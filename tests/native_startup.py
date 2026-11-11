"""Real isolated-provider startup; no supplied relocation can stand in for binding."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from contextlib import nullcontext
from toolchain import configure, sibling, target_headers


def run(argv,expected=0):
    process=subprocess.Popen(list(map(str,argv)),stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
    try:
        stdout,stderr=process.communicate(timeout=180)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid,signal.SIGKILL)
        process.communicate()
        raise AssertionError('UNKNOWN: 180-second execution guard')
    result=subprocess.CompletedProcess(argv,process.returncode,stdout,stderr)
    assert result.returncode==expected,(result.returncode,result.stderr.decode())
    return result



def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def section(path, name):
    return json.loads(path.read_text().split('\nsection '+name+'\n')[1].splitlines()[0])


def source_ir(major, kind):
    prefix=target_headers(major)+'''declare ptr @__bennett_qalloc(i64, i64)
declare void @__bennett_qfree(ptr)
declare ptr @__bennett_nz_alloc(i64)
declare void @__bennett_nz_fault(i64)
define i32 @top() {
'''
    before=' %a = call ptr @__bennett_nz_alloc(i64 1)\n' if kind=='isolation' else ''
    quantum=' %q = call ptr @__bennett_qalloc(i64 0, i64 1)\n'
    if kind=='fault':
        return prefix+quantum+' call void @__bennett_nz_fault(i64 37)\n unreachable\n}\n'
    after=''' %b = call ptr @__bennett_nz_alloc(i64 1)
 %x = ptrtoint ptr %a to i64
 %y = ptrtoint ptr %b to i64
 %delta = sub i64 %y, %x
 %bad = icmp ne i64 %delta, 1
 %result = select i1 %bad, i32 83, i32 7
 ret i32 %result
'''
    return prefix+before+quantum+' call void @__bennett_qfree(ptr %q)\n'+(after if kind=='isolation' else ' ret i32 7\n')+'}\n'


def produce(directory, major, kind, paths, plugin):
    llvm=Path(f'/usr/lib/llvm-{major}/bin')
    source=directory/(kind+'.ll')
    source.write_text(source_ir(major,kind))
    out=directory/(kind+'-production')
    run([llvm/'opt',f'-load-pass-plugin={plugin}','-passes=bennett','-bennett-dialect=0.3-r1',
         '-bennett-isa=0.9','--bennett-tier=reversible','--bennett-entry=top',
         '--bennett-layout-data-base=65536',f'-bennett-out={out}','-disable-output',source])
    return out


def command(binary,major,production,out,paths,plugin,provider=True):
    arguments=[binary,f'--bennett-llvm-major={major}','-bennett-dialect=0.3-r1','-bennett-isa=0.9',
        f'--bennett-materialised={production}/device.bc','--bennett-comparison-entry=top',
        f'--bennett-plugin={plugin}',f'--bennett-out={out}','--bennett-layout-data-base=65536',
        *[f'--bennett-{key}={paths[key]}' for key in ('runtimes','arith','sysroot')]]
    if provider:
        arguments += [f'--bennett-native-provider={sibling("bennett-native-provider")}/target/debug/libbennett_vm.so',
                      f'--bennett-native-target={sibling("bennett-native-targets")}/targets/ideal-all-to-all.json']
    return arguments


def audit_execution(executable, production, kind):
    expected=-signal.SIGILL if kind=='fault' else 7
    result=run([executable],expected)
    assert result.stdout==b'',result.stdout
    if kind=='fault':assert b'37' in result.stderr,result.stderr
    else:assert result.stderr==b'',result.stderr
    receipt=json.loads(Path(str(executable)+'.runtime.json').read_text())
    life=receipt['lifetime']
    assert life['namespace'] != 0 and life['load'] and life['binding_calls']==1 and life['entry_calls']==1,life
    assert life['qreg_new_successes']==1 and life['qreg_free_successes']==(kind!='fault'),life
    assert life['unload_status']==0 and life['signal']==(signal.SIGILL if kind=='fault' else 0),life
    assert receipt['materialised_sha256']==sha(production/'device.bc')
    assert receipt['launch_sha256']==sha(production/'top/launch.bennett')
    for row in list(receipt['inputs'].values())+[receipt['provider']]+receipt['provider_dependencies']+receipt['bootstrap_dependencies']:
        assert sha(row['path'])==row['sha256'],row
    assert b'NEEDED' not in run(['readelf','-d',str(executable)+'.component']).stdout
    return receipt


def unused_binding_control(binary,directory,major,production,paths,plugin):
    out=directory/'reference-only'
    # Reuse the adapter's actual authenticated binding name, not a guessed symbol.
    prepared=json.loads((directory/'clean-comparison/native-materialisation.json').read_text())
    reference=directory/'unused-reference.c'
    reference.write_text('__asm__(".data\\n.globl unused_binding_reference\\nunused_binding_reference:\\n.quad '+prepared['binding_symbol']+'\\n.text\\n");\n')
    result=run([*command(binary,major,production,out,paths,plugin,False),f'--bennett-native-input={reference}'],1)
    assert b'BD-E-NATIVE-STARTUP' in result.stderr and b'unused binding relocations' in result.stderr,result.stderr
    assert not (out/'native-O0').exists() and not (out/'native-O2').exists()
    manifest=json.loads((out/'manifest.json').read_text())
    assert not any(row['stage'].startswith('native-codegen') for row in manifest['commands'])


def hello_run(binary,directory,major,paths,plugin):
    llvm=Path(f'/usr/lib/llvm-{major}/bin')
    source=sibling('bennett-conformance')/'ladder/rung-3/fixtures/hello.c'
    linked=directory/'hello-linked.bc'
    run([llvm/'clang','--target=x86_64-unknown-linux-musl','-O2','-flto','-emit-llvm','-c',
         f'--sysroot={paths["sysroot"]}','-nostdinc','-isystem',paths['sysroot']/'include',
         source,'-o',directory/'hello.bc'])
    run([llvm/'llvm-link',directory/'hello.bc',paths['runtimes'],paths['arith'],'--only-needed','-o',linked])
    run([llvm/'opt','-passes=lto<O3>',linked,'-o',directory/'hello-postlink.bc'])
    production=directory/'hello-production'
    run([llvm/'opt',f'-load-pass-plugin={plugin}','-passes=bennett','-bennett-dialect=0.3-r1',
         '-bennett-isa=0.9','--bennett-tier=reversible','--bennett-entry=main',
         '--bennett-layout-data-base=65536','-bennett-budget-default=10000000,1048576,65536,256,65536',
         f'-bennett-out={production}','-disable-output',directory/'hello-postlink.bc'])
    before={p:sha(p) for p in production.rglob('*') if p.is_file()}
    out=directory/'hello-comparison'
    arguments=[str(x).replace('--bennett-comparison-entry=top','--bennett-comparison-entry=main')
               for x in command(binary,major,production,out,paths,plugin)]
    run(arguments)
    for level in ('O0','O2'):
        executable=out/('native-'+level)
        result=run([executable])
        assert result.stdout==b'hello, world\n' and result.stderr==b'',(result.stdout,result.stderr)
        record=json.loads(Path(str(executable)+'.runtime.json').read_text())
        assert record['lifetime']['binding_calls']==1 and record['lifetime']['unload_status']==0,record
        assert record['lifetime']['component_exit']==1,record
        assert record['materialised_sha256']==sha(production/'device.bc')
        assert record['launch_sha256']==sha(production/'main/launch.bennett')
    assert {p:sha(p) for p in production.rglob('*') if p.is_file()}==before
    print(f'LLVM{major} actual musl hello: exact stdout/status at O0/O2, real startup/exit, live program unloaded')


def tamper_control(executable):
    component=Path(str(executable)+'.component')
    original=component.read_bytes()
    try:
        component.write_bytes(original+b'changed')
        result=run([executable],125)
        assert b'SHA256 mismatch' in result.stderr,result.stderr
        record=json.loads(Path(str(executable)+'.runtime.json').read_text())
        assert record['status']=='failed',record
    finally:
        component.write_bytes(original)


def dirty_free_control(directory,out):
    source=Path(__file__).resolve().parent/'fixtures/native_dirty_provider.c'
    bootstrap=directory/'dirty-provider-control'
    run(['cc','-std=c11','-O2','-fPIE','-pie','-I',out,source,'-ldl','-o',bootstrap])
    for level in ('O0','O2'):
        config=json.loads(Path(str(out/('native-'+level))+'.provider-config.json').read_text())
        inputs=config['inputs'];report=directory/('dirty-'+level+'.json')
        result=run([bootstrap,inputs['component']['path'],config['provider']['path'],
                    inputs['target']['path'],inputs['object']['path'],report,str(os.getpid()),'dirty-control'],-signal.SIGILL)
        assert result.stdout==b'' and result.stderr==b'bennett runtime fault 4\n',(result.stdout,result.stderr)
        life=json.loads(report.read_text())
        assert life['load'] and life['namespace']!=0 and life['binding_calls']==1 and life['entry_calls']==1,life
        assert life['qreg_new_successes']==1 and life['qreg_free_successes']==0 and life['last_provider_status']==7,life
        assert life['signal']==signal.SIGILL and life['unload_status']==0,life


def major_run(binary,directory,major):
    directory.mkdir()
    paths=configure(major)
    plugin=sibling('bennett-plugin-r-contract')/f'build/libbennett-plugin-{major}.so'
    for kind in ('clean','isolation','fault'):
        production=produce(directory,major,kind,paths,plugin)
        before={p:sha(p) for p in production.rglob('*') if p.is_file()}
        out=directory/(kind+'-comparison')
        run(command(binary,major,production,out,paths,plugin))
        original=section(production/'top/launch.bennett','layout')
        resolved=json.loads((out/'resolved-layout.json').read_text())
        for name,value in original['globals'].items():
            assert all(resolved['globals'][name][key]==value[key] for key in ('base','size','image'))
        assert resolved['heap_base']==original['heap_base']
        for level in ('O0','O2'):
            audit_execution(out/('native-'+level),production,kind)
        if kind=='clean':
            unused_binding_control(binary,directory,major,production,paths,plugin)
            tamper_control(out/'native-O0')
            dirty_free_control(directory,out)
        assert {p:sha(p) for p in production.rglob('*') if p.is_file()}==before
        print(f'LLVM{major} {kind}: actual VM load/bind/entry/unload, both O0/O2, fixed globals/heap and immutable publication')
    hello_run(binary,directory,major,paths,plugin)


def lifetime_controls():
    script=Path(__file__).resolve().parents[1]/'scripts/native-provider-run.py'
    spec=importlib.util.spec_from_file_location('provider_receipt',script)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    valid=dict(namespace=1,binding_calls=1,entry_calls=1,unload_status=0,signal=0,status=7)
    module.validate_lifetime(valid,7)
    for change,code in [(dict(namespace=0),7),(dict(binding_calls=0),7),
                        (dict(entry_calls=0),7),(dict(unload_status=8),7),({},-9)]:
        try:module.validate_lifetime(valid|change,code)
        except ValueError:pass
        else:raise AssertionError('invalid lifetime/host termination accepted')


evidence=os.environ.get('BENNETT_DRIVER_STARTUP_EVIDENCE')
if evidence:Path(evidence).mkdir(parents=True,exist_ok=False)
lifetime_controls()
with (nullcontext(evidence) if evidence else tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'],prefix='native-startup-')) as temp:
    for major in (18,23):major_run(sys.argv[1],Path(temp)/str(major),major)
