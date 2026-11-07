"""Check actual materialised fault outcomes, independently of source UBSan."""
from toolchain import configure, sibling
import hashlib, json, pathlib, subprocess, sys, tempfile

root = pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(dir=root/'.tmp', prefix='native-faults-') as temp:
    d = pathlib.Path(temp)
    layout = d/'layout.json'
    layout.write_text(json.dumps(dict(null_size=4096, ptr_width=64, heap_base=69632,
        heap_limit_max=1048576, globals={}, interface_regions={})))
    for major in (18, 23):
        configure(major)
        # Constant operands ensure O2 cannot erase the fault into poison.
        # In particular srem(min,-1) must fault even on x86 (native gives 0).
        cases = [(op+'-zero', f'%v = {op} i32 9, 0', 5)
                 for op in ('udiv', 'urem', 'sdiv', 'srem')]
        cases += [(op+'-overflow', f'%v = {op} i32 -2147483648, -1', 6)
                  for op in ('sdiv', 'srem')]
        cases += [('explicit', 'call void @__bennett_nz_fault(i64 123456789)', 123456789),
                  ('unreachable', 'unreachable', 4),
                  ('double-free', '%p = call ptr @__bennett_nz_alloc(i64 1)\n call void @__bennett_nz_free(ptr %p)\n call void @__bennett_nz_free(ptr %p)', 7)]
        for name, body, code in cases:
            ir = d/f'{name}-{major}.ll'
            ir.write_text('declare ptr @__bennett_nz_alloc(i64)\ndeclare void @__bennett_nz_free(ptr)\ndeclare void @__bennett_nz_fault(i64)\n'
                + 'define i32 @main() {\n '+body+('' if name == 'unreachable' else '\n ret i32 0')+'\n}\n')
            digest = hashlib.sha256(ir.read_bytes()).hexdigest()
            out = d/f'{name}-{major}'
            p = subprocess.run([sys.argv[1], f'--bennett-llvm-major={major}',
                f'--bennett-materialised={ir}', f'--bennett-out={out}',
                f'--bennett-comparison-layout={layout}', '--bennett-layout-data-base=65536'],
                capture_output=True, timeout=60)
            assert p.returncode == 0, p.stderr.decode()
            assert hashlib.sha256(ir.read_bytes()).hexdigest() == digest
            for level in ('O0', 'O2'):
                p = subprocess.run([out/f'native-{level}'], capture_output=True, timeout=5)
                assert p.returncode != 0 and f'bennett runtime fault {code}\n'.encode() == p.stderr, (major, name, level, p)
            coverage = json.loads((out/'native-detection.json').read_text())
            assert coverage['subject'] == 'materialised' and coverage['general_memory'] is True
            assert coverage['division_by_zero'] and coverage['signed_division_overflow']
            assert coverage['status'] == 'instrumented' and coverage['infrastructure_exit_status'] == 125
