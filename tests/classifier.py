"""Source classifiers are distinct from the optimised materialised comparison."""
from toolchain import configure, sibling
import hashlib, json, pathlib, subprocess, sys, tempfile

root = pathlib.Path(__file__).resolve().parents[1]
def run(args):
    p = subprocess.run(list(map(str, args)), capture_output=True, timeout=60)
    assert p.returncode == 0, p.stderr.decode()
    return p.stdout

with tempfile.TemporaryDirectory(dir=root/'.tmp', prefix='classifier-') as temp:
    d = pathlib.Path(temp)
    for major in (18, 23):
        configure(major)
        llvm = pathlib.Path(f'/usr/lib/llvm-{major}/bin')
        source = d/f'original-{major}.c'
        # This source deliberately differs from the already-materialised input.
        # Its diagnostics must never be substituted for the latter's results.
        source.write_text('int main(void) { int a[2]; volatile int i=2; a[i]=7; return 0; }\n')
        materialised = d/f'device-{major}.ll'
        materialised.write_text('define i32 @main() { ret i32 0 }\n')
        digest = hashlib.sha256(materialised.read_bytes()).hexdigest()
        layout = d/f'layout-{major}.json'
        # Extra UBSan string/guard data needs more than the primitive-only page.
        layout.write_text(json.dumps(dict(null_size=4096, ptr_width=64,
            heap_base=131072, heap_limit_max=1048576, globals={}, interface_regions={})))
        out = d/f'out-{major}'
        run([sys.argv[1], f'--bennett-llvm-major={major}',
             f'--bennett-materialised={materialised}', f'--bennett-out={out}',
             f'--bennett-comparison-layout={layout}', '--bennett-layout-data-base=126976',
             f'--bennett-classifier-input={source}'])
        assert hashlib.sha256(materialised.read_bytes()).hexdigest() == digest
        for level in ('O0', 'O2'):
            assert run([out/f'native-{level}']) == b''
        rows = json.loads((out/'native-classifiers.json').read_text())
        assert len(rows) == 2, rows
        row = rows[0]
        assert row['variant'] == 'O0-UBSan-minimal-original-input' and row['status'] == 'linked', rows
        assert row['subject'] == 'original-input', row
        assert row['inputs'][0]['sha256'] == hashlib.sha256(source.read_bytes()).hexdigest()
        assert rows[1]['variant'] == 'O0-ASan-original-input'
        assert rows[1]['blocked_on'] == ['freestanding-asan-runtime']
        binary = out/'classifier-ubsan-minimal'
        p = subprocess.run([binary], capture_output=True, timeout=10)
        assert p.returncode != 0 and b'ubsan: out-of-bounds' in p.stderr, p
        assert not run([llvm/'llvm-nm', '--undefined-only', binary]).strip()
        assert b'INTERP' not in run(['readelf', '-l', binary])
        commands = json.loads((out/'manifest.json').read_text())['commands']
        source_commands = [c for c in commands if c['stage'] == 'classifier-frontend']
        assert source_commands and '-fsanitize=undefined' in source_commands[0]['argv']
        for c in commands:
            if c['stage'].startswith('comparison-'):
                assert not any(pathlib.Path(a).name.startswith('classifier-') for a in c['argv']), c
