"""Consume the authenticated R global-to-native handoff without moving ISA ranges."""
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
from toolchain import configure, sibling, target_headers


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def section(path, name):
    return json.loads(path.read_text().split(f'\nsection {name}\n', 1)[1].splitlines()[0])


def assert_invalid_handoffs(directory, major, production, prepared):
    script = pathlib.Path(__file__).resolve().parents[1] / 'scripts/native-layout.py'
    original = prepared['device_globals']['G1']
    cases = [('record', dict(record_sha256='0' * 64)),
             ('materialised', dict(materialised_sha256='0' * 64)),
             ('launch', dict(launch_sha256='0' * 64)), ('entry', dict(entries=['other'])),
             ('missing', dict(device_globals={})),
             ('unknown', dict(device_globals=prepared['device_globals'] | {'G999': original})),
             ('duplicate-source', dict(symbols=prepared['symbols'] + [prepared['symbols'][0]]))]
    for field, value in [('base', 8192), ('size', 14), ('source_key', 'name:other'),
                         ('native_symbol', 'wrong_symbol')]:
        cases.append((field, dict(device_globals=prepared['device_globals'] | {'G1': original | {field: value}})))
    for name, change in cases:
        report = directory / f'invalid-{major}-{name}.json'
        report.write_text(json.dumps(prepared | change))
        out = directory / f'invalid-{major}-{name}'
        out.mkdir()
        result = subprocess.run([sys.executable, str(script), str(out), str(production / 'device.bc'),
            '', '4096', '', str(report), str(production / 'main/launch-record.json'), 'main'],
            capture_output=True)
        assert result.returncode == 1 and b'BD-E-NATIVE-LAYOUT' in result.stderr, (name, result.stderr)
        assert not (out / 'resolved-layout.json').exists(), name


def assert_publication_integrity(directory, major, production, prepared, layout):
    script = pathlib.Path(__file__).resolve().parents[1] / 'scripts/native-layout.py'
    report = directory / f'prepared-{major}.json'
    report.write_text(json.dumps(prepared))
    explicit = directory / f'explicit-{major}.json'
    explicit.write_text(json.dumps(layout))
    for name in ('device.bc', 'main/build.json', 'main/launch.bennett', 'main/launch-record.json'):
        copy = directory / f'changed-{major}-{pathlib.Path(name).stem}'
        (copy / 'main').mkdir(parents=True)
        for artifact in ('device.bc', 'main/build.json', 'main/launch.bennett', 'main/launch-record.json'):
            shutil.copyfile(production / artifact, copy / artifact)
        with (copy / name).open('ab') as changed:
            changed.write(b'\n')
        out = copy / 'comparison'
        out.mkdir()
        result = subprocess.run([sys.executable, str(script), str(out), str(copy / 'device.bc'),
            str(explicit), '4096', '', str(report), str(copy / 'main/launch-record.json'), 'main'],
            capture_output=True)
        assert result.returncode == 1 and b'SHA256 mismatch' in result.stderr, (name, result.stderr)
        assert not (out / 'resolved-layout.json').exists(), name


def assert_explicit_handoff(directory, major, production, prepared, layout):
    script = pathlib.Path(__file__).resolve().parents[1] / 'scripts/native-layout.py'
    report = directory / f'explicit-report-{major}.json'
    report.write_text(json.dumps(prepared))
    binding = layout['globals']['G1']
    cases = [('valid', {}), ('symbol', dict(globals=layout['globals'] | {
        'G1': binding | dict(native_symbol='wrong_symbol')})),
        ('address', dict(globals=layout['globals'] | {'G1': binding | dict(base=8192)})),
        ('stale', dict(materialised_sha256='0' * 64))]
    for name, change in cases:
        explicit = directory / f'explicit-{major}-{name}.json'
        explicit.write_text(json.dumps(layout | change))
        out = directory / f'explicit-{major}-{name}'
        out.mkdir()
        result = subprocess.run([sys.executable, str(script), str(out), str(production / 'device.bc'),
            str(explicit), '4096', '', str(report), str(production / 'main/launch-record.json'), 'main'],
            capture_output=True)
        if name == 'valid':
            assert result.returncode == 0, result.stderr
            resolved = json.loads((out / 'resolved-layout.json').read_text())
            assert resolved['globals']['G1']['native_symbol'] == prepared['device_globals']['G1']['native_symbol']
        else:
            assert result.returncode == 1 and b'BD-E-NATIVE-LAYOUT' in result.stderr, (name, result.stderr)
            assert not (out / 'resolved-layout.json').exists(), name


def assert_mapping(directory, major, production, out, before, launch, layout):
    device = production / 'device.bc'
    receipt_path = production / 'main/launch-record.json'
    prepared = json.loads((out / 'native-preparation.json').read_text())
    assert prepared['materialised_sha256'] == before[device]
    assert prepared['record_sha256'] == before[receipt_path]
    assert prepared['resolved_link_layout'] is False
    native_globals = [s for s in prepared['symbols'] if s['kind'] == 'global']
    message = next(s for s in native_globals if s['llvm_name'] == 'message')
    assert message['source_key'] == 'name:message' and message['native_symbol']
    assert message['size'] == 13 and message['alignment'] == 1
    mapping = prepared['device_globals']['G1']
    assert mapping == dict(source_key=message['source_key'], native_symbol=message['native_symbol'],
                           base=4096, size=13), mapping
    assert prepared['launch_sha256'] == before[launch]
    assert prepared['entries'] == ['main']
    resolved = json.loads((out / 'resolved-layout.json').read_text())
    assert resolved['globals']['G1'] == layout['globals']['G1'] | dict(
        native_symbol=message['native_symbol'], llvm_name='message', alignment=1)
    assert resolved['materialised_sha256'] == before[device]
    assert len(resolved['native_bindings']) == len(layout['globals'])
    assert next(b for b in resolved['native_bindings'] if b['key'] == 'global G1') == dict(
        key='global G1', base=4096, size=13, alignment=1, native_symbol=message['native_symbol'],
        sections=['.data.message', '.bss.message', '.rodata.message'])
    assert_invalid_handoffs(directory, major, production, prepared)
    assert_publication_integrity(directory, major, production, prepared, layout)
    assert_explicit_handoff(directory, major, production, prepared, layout)

def run_major(binary, directory, major):
    paths = configure(major)
    plugin = sibling('bennett-plugin-r-contract') / f'build/libbennett-plugin-{major}.so'
    source = directory / f'global-{major}.ll'
    source.write_text(target_headers(major) + '''@message = private unnamed_addr constant [13 x i8] c"Hello world!\\00", align 1
declare i32 @puts(ptr)
define i32 @main() {
  %value = call i32 @puts(ptr @message)
  ret i32 0
}
''')
    linked = directory / f'linked-{major}.bc'
    closure = subprocess.run([
        f'/usr/lib/llvm-{major}/bin/llvm-link', str(source), str(paths['runtimes']),
        str(paths['arith']), '--only-needed', '-o', str(linked)], capture_output=True)
    assert closure.returncode == 0, closure.stderr.decode()
    production = directory / f'production-{major}'
    produced = subprocess.run([
        f'/usr/lib/llvm-{major}/bin/opt', f'-load-pass-plugin={plugin}',
        '-passes=bennett', '-bennett-dialect=0.3-r1', '-bennett-isa=0.9',
        '--bennett-tier=reversible', '--bennett-entry=main',
        f'-bennett-out={production}', '-disable-output', str(linked)], capture_output=True)
    assert produced.returncode == 0, produced.stderr.decode()
    launch = production / 'main/launch.bennett'
    layout = section(launch, 'layout')
    assert layout['globals']['G1'] == dict(base=4096, image='G1', size=13), layout
    symbols = section(launch, 'symbols')
    assert any(s['kind'] == 'data' and s['name'] == 'G1' for s in symbols.values())
    build = json.loads((production / 'main/build.json').read_text())
    assert build['layout'] == layout
    receipt_path = production / 'main/launch-record.json'
    receipt = json.loads(receipt_path.read_text())
    assert set(receipt) == {'schema', 'entry', 'artifacts'}, receipt
    for name, artifact in receipt['artifacts'].items():
        assert sha(production / name) == artifact['sha256'], name
    before = {p: sha(p) for p in production.rglob('*') if p.is_file()}
    out = directory / f'comparison-{major}'
    result = subprocess.run([
        binary, f'--bennett-llvm-major={major}', '-bennett-dialect=0.3-r1',
        '-bennett-isa=0.9', '--bennett-tier=reversible', '--bennett-entry=main',
        f'--bennett-plugin={plugin}', f'--bennett-plugin-sha256={sha(plugin)}',
        *[f'--bennett-{key}={paths[key]}' for key in ('runtimes', 'arith')],
        f'--bennett-materialised={production}/device.bc', f'-bennett-out={out}'],
        capture_output=True)
    # This fixture owns layout consumption; real program startup is separate.
    assert result.returncode == 1 and b'BD-E-NATIVE-STARTUP' in result.stderr, result.stderr.decode()
    manifest = json.loads((out / 'manifest.json').read_text())
    provenance = manifest['native_materialisation']
    assert provenance['materialised']['sha256'] == before[production / 'device.bc']
    assert provenance['launch_record']['sha256'] == before[receipt_path]
    assert provenance['plugin']['sha256'] == sha(plugin)
    stages = {c['stage']: c for c in manifest['commands']}
    assert stages['native-prepare']['success'] and stages['comparison-checks']['success']
    assert stages['native-layout']['success'] and stages['native-finalise']['success']
    assert_mapping(directory, major, production, out, before, launch, layout)
    assert (out / 'comparison.ld').is_file()
    assert not (out / 'native-O0').exists() and not (out / 'native-O2').exists()
    assert {p: sha(p) for p in production.rglob('*') if p.is_file()} == before
    print(f'LLVM{major}: authenticated G1 native mapping consumed at device base4096; real startup remains required')


with tempfile.TemporaryDirectory(dir=pathlib.Path(__file__).resolve().parents[1] / '.tmp',
                                 prefix='r-native-layout-') as temp:
    failures = []
    for major in (18, 23):
        try:
            run_major(sys.argv[1], pathlib.Path(temp), major)
        except (AssertionError, KeyError, StopIteration) as error:
            failures.append(f'LLVM{major}: {error}')
    assert not failures, '\n'.join(failures)
