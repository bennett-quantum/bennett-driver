"""Pin the missing R global-to-native handoff at the published producer pin."""
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
from toolchain import configure, sibling, target_headers


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def section(path, name):
    return json.loads(path.read_text().split(f'\nsection {name}\n', 1)[1].splitlines()[0])


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
    diagnostic = 'BD-E-NATIVE-LAYOUT: §19.5 missing native symbol mapping for global G1'
    assert result.returncode == 1 and diagnostic in result.stderr.decode(), result.stderr.decode()
    manifest = json.loads((out / 'manifest.json').read_text())
    provenance = manifest['native_materialisation']
    assert provenance['materialised']['sha256'] == before[production / 'device.bc']
    assert provenance['launch_record']['sha256'] == before[receipt_path]
    assert provenance['plugin']['sha256'] == sha(plugin)
    stages = {c['stage']: c for c in manifest['commands']}
    assert stages['native-prepare']['success'] and stages['comparison-checks']['success']
    assert not stages['native-layout']['success']
    prepared = json.loads((out / 'native-preparation.json').read_text())
    assert prepared['materialised_sha256'] == before[production / 'device.bc']
    assert prepared['record_sha256'] == before[receipt_path]
    assert prepared['resolved_link_layout'] is False
    native_globals = [s for s in prepared['symbols'] if s['kind'] == 'global']
    message = next(s for s in native_globals if s['llvm_name'] == 'message')
    assert message['source_key'] == 'name:message' and message['native_symbol']
    assert message['size'] == 13 and message['alignment'] == 1
    # The report names LLVM/native globals but supplies neither their object
    # global IDs (G1) nor their resolved bases. Ordering/size is not a join key.
    assert all('base' not in s and 'G1' not in s.values() for s in native_globals)
    assert not any(c['stage'] == 'native-finalise' for c in manifest['commands'])
    for name in ('resolved-layout.json', 'comparison.ld', 'native-O0', 'native-O2'):
        assert not (out / name).exists(), name
    assert {p: sha(p) for p in production.rglob('*') if p.is_file()} == before
    print(f'LLVM{major}: published G1/base and LLVM/native symbols lack a join; {diagnostic}')


with tempfile.TemporaryDirectory(dir=pathlib.Path(__file__).resolve().parents[1] / '.tmp',
                                 prefix='r-native-layout-') as temp:
    failures = []
    for major in (18, 23):
        try:
            run_major(sys.argv[1], pathlib.Path(temp), major)
        except (AssertionError, KeyError, StopIteration) as error:
            failures.append(f'LLVM{major}: {error}')
    assert not failures, '\n'.join(failures)
