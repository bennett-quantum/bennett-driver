"""Real process-prepared musl closure; explicitly NOT materialised R acceptance."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from toolchain import configure, flags, sibling

ROOT = Path(__file__).resolve().parents[1]
DRIVER = Path(sys.argv[1]).resolve()
# Independently derived in the C fixtures; the tail is flushed only on return.
CASES = {
    'hello': (b'hello, world\n', 0x11000),
    'integer-printf': (b'[  musl] -00042 37 002a !\ntail:007', 0x12000),
}


def run(argv):
    result = subprocess.run(list(map(str, argv)), capture_output=True, timeout=120)
    assert result.returncode == 0, (argv, result.returncode, result.stderr.decode())
    return result.stdout


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'], prefix='native-scalar-') as temp:
    directory = Path(temp)
    for major in (18, 23):
        paths = configure(major)
        plugin = sibling('bennett-plugin-native-comparison') / f'build/libbennett-plugin-{major}.so'
        llvm = Path(f'/usr/lib/llvm-{major}/bin')
        for case, (expected, heap_base) in CASES.items():
            source = ROOT / f'tests/fixtures/r3-{case}.c'
            source_sha = digest(source)
            prepared = directory / f'{case}-prepared-{major}'
            run([DRIVER, *flags(major, plugin=False), f'--bennett-plugin={plugin}',
                 f'--bennett-plugin-sha256={digest(plugin)}', '-bennett-dialect=0.2.13',
                 f'--bennett-llvm-major={major}', '--bennett-tier=reversible',
                 '--bennett-entry=main', '--bennett-emit=process-bitcode',
                 f'--bennett-out={prepared}', source])
            manifest = json.loads((prepared / 'manifest.json').read_text())
            assert manifest['status'] == 'prepared'
            assert not (prepared / 'device.bc').exists(), 'preparation cannot claim materialisation'
            assert not (prepared / 'launches.json').exists()
            assert digest(source) == source_sha
            module = prepared / 'process-prepared.bc'
            module_sha = digest(module)
            assert manifest['process_preparation']['module']['sha256'] == module_sha
            wrapper = run([llvm / 'llvm-dis', prepared / 'process-entry.bc', '-o', '-']).decode()
            user_entry = json.loads((prepared / 'process-entry.json').read_text())['user_entry']
            body = wrapper.split('define i32 @main(', 1)[1].split('\n}', 1)[0]
            assert body.index('@__bennett_rt_prepare_process(') < body.index('@' + user_entry + '(')
            assert '@exit(' in body and 'unreachable' in body
            if case == 'integer-printf':
                frontend = (prepared / 'input-0.ll').read_text()
                assert 'call i32 (ptr, ...) @printf' in frontend, 'formatted workload must retain varargs'
            # The pinned real closure's ELF data end is in [0x10000,0x11000)
            # for hello and [0x11000,0x12000) for formatted printf. Keep the
            # exact page assertion and independently audit it in both ELFs.
            layout = directory / f'{case}-layout-{major}.json'
            layout.write_text(json.dumps(dict(null_size=4096, ptr_width=64,
                heap_base=heap_base, heap_limit_max=1048576, globals={}, interface_regions={})))
            output = directory / f'{case}-native-{major}'
            run([DRIVER, f'--bennett-llvm-major={major}', f'--bennett-materialised={module}',
                 f'--bennett-out={output}', f'--bennett-comparison-layout={layout}',
                 '--bennett-layout-data-base=65536'])
            records = json.loads((output / 'native-comparisons.json').read_text())
            assert [record['status'] for record in records] == ['linked', 'linked', 'blocked']
            assert records[2]['blocked_on'] == ['freestanding-asan-runtime']
            for record in records[:2]:
                assert record['provenance'] == 'explicit module; producer receipt not verified'
                inputs = record['inputs']
                assert inputs['materialised']['sha256'] == module_sha
                assert inputs['native_support']['sha256'] == digest(paths['native-support'])
                assert inputs['runtimes']['sha256'] == digest(paths['runtimes'])
                assert inputs['arith']['sha256'] == digest(paths['arith'])
                for value in inputs.values():
                    assert digest(Path(value['path'])) == value['sha256'], value
                binary = output / ('native-' + record['variant'])
                observed = subprocess.run([binary], capture_output=True, timeout=10)
                assert (observed.returncode, observed.stdout, observed.stderr) == (0, expected, b''), (
                    major, case, record['variant'], observed)
                assert not run([llvm / 'llvm-nm', '--undefined-only', binary]).strip()
                assert b'INTERP' not in run(['readelf', '-l', binary])
                assert b'NEEDED' not in run(['readelf', '-d', binary])
                symbols = run([llvm / 'llvm-nm', '--defined-only', '--format=posix', binary]).decode()
                addresses = {fields[0]: int(fields[2], 16) for line in symbols.splitlines()
                             if len(fields := line.split()) >= 3}
                data_end = addresses['__bennett_comparison_data_end']
                assert (data_end + 4095) // 4096 * 4096 == heap_base
                assert addresses['_start'] >= 0x400000
                argv = record['link_argv']
                assert {'-nostdlib', '-nostdinc', '-static', '-no-pie'} <= set(argv)
                assert not {'-lc', '-lm', '-shared'} & set(argv)
            assert digest(module) == module_sha, 'native build must preserve the prepared input'
            print(f'LLVM{major} {case}: real prepared musl, static O0/O2 stdout exact; '
                  'full R/native agreement remains blocked upstream')
