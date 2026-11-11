"""Generate the driver-owned gateway and audit the explicitly selected provider."""
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def dependencies(path):
    result = subprocess.run(['ldd', str(path)], capture_output=True, text=True, check=True)
    paths = {pathlib.Path(path).resolve()}
    for line in result.stdout.splitlines():
        value = line.strip().split('=>', 1)[-1].strip().split(' ', 1)[0]
        if value.startswith('/'):
            paths.add(pathlib.Path(value).resolve())
        elif 'not found' in line:
            raise ValueError('BD-E-NATIVE-PROVIDER: missing dependency: '+line)
    return [dict(path=str(p), sha256=sha(p)) for p in sorted(paths)]


def prepare(out, entry, receipt_path, provider, target, selected):
    out, receipt_path = pathlib.Path(out), pathlib.Path(receipt_path)
    report = json.loads((out/'native-materialisation.json').read_text())
    receipt = json.loads(receipt_path.read_text())
    obj = receipt_path.parent/'launch.bennett'
    if report['entries'] != [entry] or receipt['entry'] != entry:
        raise ValueError('BD-E-NATIVE-PROVIDER: selected entry mismatch')
    launch_sha=report.get('launch_sha256',receipt['artifacts'][entry+'/launch.bennett']['sha256'])
    if report['record_sha256'] != sha(receipt_path) or launch_sha != sha(obj):
        raise ValueError('BD-E-NATIVE-PROVIDER: publication identity changed')
    original=json.loads(obj.read_text().split('\nsection layout\n',1)[1].splitlines()[0])
    resolved=json.loads((out/'resolved-layout.json').read_text())
    for field in ('null_size','ptr_width','heap_base','heap_limit_max'):
        if original[field]!=resolved[field]:
            raise ValueError('BD-E-NATIVE-PROVIDER: shared layout differs: '+field)
    for name,value in original['globals'].items():
        if name not in resolved['globals'] or any(value[k]!=resolved['globals'][name][k] for k in ('base','size','image')):
            raise ValueError('BD-E-NATIVE-PROVIDER: shared global differs: '+name)
    ir = (out/'native-finalised.ll').read_text()
    # Only the native calling harness uses the C process ABI; other selected
    # callable signatures remain expressible through an explicit native input.
    has_main=bool(re.search(r'^define\b[^\n]*@main\(',ir,re.M))
    rows = [s for s in report['symbols'] if s.get('llvm_name') == selected and s['kind'] == 'function']
    symbol = rows[0]['native_symbol'] if rows else selected
    match = re.search(r'^define\b[^\n]*?\bi32\s+@'+re.escape(selected)+r'\(([^\n)]*)\)', ir, re.M)
    if not match:
        raise ValueError('BD-E-NATIVE-PROVIDER: supply an i32 C main native input for this callable root')
    params = match[1].strip()
    count = 0 if not params else len(params.split(','))
    if count not in (0, 2, 3):
        raise ValueError('BD-E-NATIVE-PROVIDER: native input main requires 0, 2 or 3 C parameters')
    declaration = {0: 'void', 2: 'int,char **', 3: 'int,char **,char **'}[count]
    arguments = {0: '', 2: 'argc,argv', 3: 'argc,argv,envp'}[count]
    replacements = {
        '/* DRIVER_ENTRY_DECL */': f'extern int driver_entry({declaration}) __asm__({json.dumps(symbol)});',
        '/* DRIVER_MAIN_STUB */': '' if has_main else 'int main(void) { return 0; }',
        'DRIVER_BINDING_SYMBOL': report['binding_symbol'],
        '/* DRIVER_INPUTS */': '__bennett_rt_native_inputs(argc,argv,envp);' if count else '(void)argc;(void)argv;(void)envp;',
        '/* DRIVER_ENTRY_CALL */': f'driver_entry({arguments})',
        '/* DRIVER_FINISH */': 'extern void exit(int); exit(result);' if selected == 'main' else '',
    }
    source = (out/'native-component.c').read_text()
    for old, new in replacements.items():
        source = source.replace(old, new)
    (out/'native-component.c').write_text(source)
    shutil.copyfile(obj, out/'native-selected.bennett')
    shutil.copyfile(target, out/'native-target.json')
    plan = dict(schema='bennett-driver-isolated-provider-1', entry=entry,
                binding_symbol=report['binding_symbol'], provider=dict(path=str(pathlib.Path(provider).resolve()), sha256=sha(provider)),
                dependencies=dependencies(provider), launch_sha256=sha(obj), record_sha256=sha(receipt_path),
                materialised_sha256=report['materialised_sha256'])
    (out/'native-provider-plan.json').write_text(json.dumps(plan,sort_keys=True)+'\n')


def wrap(out, executable, component, template):
    out, executable, component = map(pathlib.Path, (out, executable, component))
    plan = json.loads((out/'native-provider-plan.json').read_text())
    inputs = dict(component=component, bootstrap=out/'native-bootstrap', object=out/'native-selected.bennett', target=out/'native-target.json')
    config = dict(plan, inputs={k:dict(path=str(p.resolve()),sha256=sha(p)) for k,p in inputs.items()},
                  bootstrap_dependencies=dependencies(out/'native-bootstrap'))
    path = pathlib.Path(str(executable)+'.provider-config.json')
    path.write_text(json.dumps(config,sort_keys=True)+'\n')
    component.chmod(0o644)
    source = pathlib.Path(template).read_text().replace('DRIVER_CONFIG_SHA256',sha(path))
    executable.write_text(source)
    executable.chmod(0o755)


if sys.argv[1] == 'prepare':
    prepare(*sys.argv[2:])
else:
    wrap(*sys.argv[2:])
