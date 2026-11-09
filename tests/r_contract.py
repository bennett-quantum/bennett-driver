"""Classical R identity migration, dialect §§1.7/19.9/23; ISA §§4.9/10."""
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
from toolchain import configure, sibling, target_headers

root = pathlib.Path(__file__).resolve().parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run_major(major, binary, directory):
    paths = configure(major)
    plugin = sibling('bennett-plugin-r-contract') / f'build/libbennett-plugin-{major}.so'
    libraries = [f'--bennett-{key}={paths[key]}' for key in ('runtimes', 'arith')]
    libraries += [f'--bennett-plugin={plugin}', f'--bennett-plugin-sha256={sha(plugin)}']
    source = directory / f'main-{major}.ll'
    source.write_text(target_headers(major) + '''define i32 @main() { ret i32 7 }
!llvm.module.flags = !{!0}
!0 = !{i32 1, !"bennett.dialect", !"0.3-r1"}
''')
    common = [binary, f'--bennett-llvm-major={major}', '-bennett-dialect=0.3-r1',
              '--bennett-tier=reversible', '--bennett-entry=main', *libraries]
    out = directory / f'production-{major}'
    assert_production_invocation(common, source, directory, major)
    # Produce this fixture with the published plugin, independently of driver
    # process preparation. This exercises comparison of genuine R materialisation.
    producer = [f'/usr/lib/llvm-{major}/bin/opt', f'-load-pass-plugin={plugin}',
                '-passes=bennett', '-bennett-dialect=0.3-r1', '-bennett-isa=0.9',
                '--bennett-tier=reversible', '--bennett-entry=main',
                f'-bennett-out={out}', '-disable-output', str(source)]
    result = subprocess.run(producer, capture_output=True)
    assert result.returncode == 0, result.stderr.decode()
    certificate = json.loads((out / 'main/certificate.json').read_text())
    assert certificate['bindings']['dialect_mapping_version'] == '0.3'
    assert certificate['producer']['materialisation']['normaliser_version'] == '0.2.8'
    assert (out / 'main/launch.bennett').read_text().startswith('bennett-object isa=0.9 object=0.9 launch=0.9 sched=0.9 cert=0.9 coverage=0.9 target=0.9 ')
    before = sha(out / 'device.bc')
    compare = directory / f'comparison-{major}'
    result = subprocess.run([*common, f'--bennett-materialised={out}/device.bc',
                            f'-bennett-out={compare}'], capture_output=True)
    assert (compare / 'manifest.json').is_file(), result.stderr.decode()
    manifest = json.loads((compare / 'manifest.json').read_text())
    assert 'native_materialisation' in manifest, result.stderr.decode()
    assert (manifest['dialect'], manifest['isa'], manifest['dialect_version'], manifest['isa_version'],
            manifest['replay_profile']) == ('0.3-r1', '0.9', '0.3-r1', '0.9', 'saved-tape-v1')
    provenance = manifest['native_materialisation']
    assert provenance['materialised']['sha256'] == before == sha(out / 'device.bc')
    assert provenance['plugin']['sha256'] == sha(plugin)
    assert provenance['launch_record']['sha256'] == sha(out / 'main/launch-record.json')
    assert 'BD-B-ISA7' not in result.stderr.decode(), result.stderr.decode()
    # Admission/provenance evidence only. Layout/startup/executor outcomes are
    # separate from contract negotiation and are covered by their own fixtures.
    assert next(c for c in manifest['commands'] if c['stage'] == 'plugin-identity')['success']
    assert any(c['stage'] == 'native-prepare' for c in manifest['commands'])
    assert_stale_flags(common, source, directory, major)
    assert_plugin_refusals(common, out, directory, major, before, plugin)
    print(f'LLVM{major}: independent R object, selected ISA0.9 manifest, comparison provenance, stale flags/plugin identity/hash rejection')

def assert_production_invocation(common, source, directory, major):
    out = directory / f'driver-production-{major}'
    result = subprocess.run([*common, f'-bennett-out={out}', str(source)], capture_output=True)
    assert (out / 'manifest.json').is_file(), result.stderr.decode()
    manifest = json.loads((out / 'manifest.json').read_text())
    assert manifest['plugin']['identity'] == 'dialect-0.3-r1;isa-0.9'
    invocation = next(c['argv'] for c in manifest['commands'] if c['stage'] == 'plugin')
    assert '-bennett-dialect=0.3-r1' in invocation and '-bennett-isa=0.9' in invocation
    assert (manifest['dialect_version'], manifest['isa_version'], manifest['replay_profile']) == ('0.3-r1', '0.9', 'saved-tape-v1')
    assert b'BD-B-ISA7' not in result.stderr

def assert_stale_flags(common, source, directory, major):
    for version in ('0.2.13', '0.3'):
        source.write_text(source.read_text().replace('!"0.3-r1"', f'!"{version}"'))
        refused = directory / f'flag-{major}-{version}'
        result = subprocess.run([*common, f'-bennett-out={refused}', str(source)], capture_output=True)
        assert result.returncode != 0 and b'BD-E-VERSION' in result.stderr, result.stderr.decode()
        assert b'BD-B-ISA7' not in result.stderr
        assert not (refused / 'device.bc').exists()
        source.write_text(source.read_text().replace(f'!"{version}"', '!"0.3-r1"'))

def assert_plugin_refusals(common, production, directory, major, digest, plugin):
    wrong = sibling('bennett-plugin-native-comparison') / f'build/libbennett-plugin-{major}.so'
    for label, selected, pin in [('identity', wrong, sha(wrong)), ('hash', plugin, '0' * 64)]:
        args = [arg for arg in common if not arg.startswith(('--bennett-plugin=', '--bennett-plugin-sha256='))]
        out = directory / f'{label}-{major}'
        result = subprocess.run([*args, f'--bennett-plugin={selected}', f'--bennett-plugin-sha256={pin}',
                                 f'--bennett-materialised={production}/device.bc', f'-bennett-out={out}'], capture_output=True)
        assert result.returncode != 0 and b'BD-E-VERSION' in result.stderr, result.stderr.decode()
        assert b'BD-B-ISA7' not in result.stderr
        assert not (out / 'native-prepared.bc').exists()
        assert sha(production / 'device.bc') == digest

with tempfile.TemporaryDirectory(dir=root / '.tmp', prefix='r-contract-') as temp:
    failures = []
    for major in (18, 23):
        try:
            run_major(major, sys.argv[1], pathlib.Path(temp))
        except AssertionError as error:
            failures.append(f'LLVM{major}: {error}')
    assert not failures, '\n'.join(failures)
