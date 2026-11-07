"""A genuine scalar R artifact needs launch binding before native startup."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from toolchain import configure, sibling

ROOT = Path(__file__).resolve().parents[1]
DRIVER = Path(sys.argv[1]).resolve()


def run(argv, **kwargs):
    return subprocess.run(list(map(str, argv)), capture_output=True, timeout=90, **kwargs)


def success(argv, **kwargs):
    result = run(argv, **kwargs)
    assert result.returncode == 0, (argv, result.stderr)
    return result.stdout


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'], prefix='native-scalar-binding-') as temp:
    directory = Path(temp)
    for major in (18, 23):
        paths = configure(major)
        llvm = Path(f'/usr/lib/llvm-{major}/bin')
        plugin = sibling('bennett-plugin-native-comparison') / f'build/libbennett-plugin-{major}.so'
        row = directory / str(major)
        row.mkdir()
        # Use the strongest real materialisation the pinned producer supplies:
        # original scalar musl hello, without the driver's process wrapper.
        # The full process-prepared R closure remains a separate blocker.
        success([llvm / 'clang', '--target=x86_64-unknown-linux-musl', '-O2', '-flto',
                 '-emit-llvm', '-c', f'--sysroot={paths["sysroot"]}', '-nostdinc',
                 '-isystem', paths['sysroot'] / 'include', ROOT / 'tests/fixtures/r3-hello.c',
                 '-o', row / 'input.bc'])
        success([llvm / 'llvm-link', row / 'input.bc', paths['runtimes'], paths['arith'],
                 '--only-needed', '-o', row / 'linked.bc'])
        success([llvm / 'opt', '-passes=lto<O3>', row / 'linked.bc', '-o', row / 'postlink.bc'])
        production = row / 'production'
        result = run([llvm / 'opt', f'-load-pass-plugin={plugin}', '-passes=bennett',
            '-bennett-dialect=0.2.13', '-bennett-isa=0.8', f'-bennett-out={production}',
            '-bennett-tier=reversible', '-bennett-entry=main',
            '-bennett-budget-default=10000000,1048576,65536,256,65536',
            row / 'postlink.bc', '-disable-output'],
            env=dict(os.environ, BENNETT_ARITH_BITCODE=str(paths['arith'])))
        assert result.returncode == 3 and b'blocked:BD-B-ISA7' in result.stderr, result.stderr
        device = production / 'device.bc'
        device_sha = digest(device)
        record_sha = digest(production / 'main/launch-record.json')
        # The actual R shadow-stack bookkeeping makes data_end 0x210a40
        # (LLVM23 O2: 0x210a60); the exact next page is 0x211000.
        layout = row / 'layout.json'
        layout.write_text(json.dumps(dict(null_size=4096, ptr_width=64,
            heap_base=0x211000, heap_limit_max=1048576, globals={}, interface_regions={})))
        output = row / 'native'
        result = run([DRIVER, f'--bennett-llvm-major={major}', '-bennett-dialect=0.2.13',
            f'--bennett-plugin={plugin}', f'--bennett-plugin-sha256={digest(plugin)}',
            f'--bennett-materialised={device}', '--bennett-comparison-entry=main',
            f'--bennett-out={output}', f'--bennett-comparison-layout={layout}',
            '--bennett-layout-data-base=65536'])
        assert result.returncode != 0 and b'BD-E-NATIVE-STARTUP' in result.stderr, result.stderr
        assert not (output / 'native-O2').exists() and not (output / 'native-O0').exists()
        assert digest(device) == device_sha
        assert digest(production / 'main/launch-record.json') == record_sha
        report = json.loads((output / 'native-materialisation.json').read_text())
        assert report['source_mode'] == 'reversible' and report['binding_symbol']
        assert report['materialised_sha256'] == device_sha and report['record_sha256'] == record_sha
        assert report['full_comparison_acceptance'] is False
        blockers = json.loads((output / 'blockers.json').read_text())
        assert blockers[0]['code'] == 'BD-E-NATIVE-STARTUP', blockers
        assert report['binding_symbol'] in blockers[0]['diagnostic']
        manifest = json.loads((output / 'manifest.json').read_text())
        stages = [command['stage'] for command in manifest['commands']]
        assert stages.index('native-prepare') < stages.index('comparison-checks') < stages.index('native-finalise')
        assert manifest['status'] == 'failed'
        print(f'LLVM{major}: actual scalar R prepare/check/finalise; '
              'blocked: real program binding/startup required, no executable emitted')
