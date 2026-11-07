"""Independent materialised-memory cases through the driver's actual links."""
from toolchain import configure, sibling
import hashlib, json, pathlib, resource, subprocess, sys, tempfile

root = pathlib.Path(__file__).resolve().parents[1]
def run(args):
    p = subprocess.run(list(map(str,args)),capture_output=True,timeout=120)
    assert p.returncode == 0, p.stderr.decode()
    return p.stdout
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

allocate = '%p = call ptr @__bennett_nz_alloc(i64 4)\n'
cases = [
    ('live', allocate+'store i32 17, ptr %p\n%v = load i32, ptr %p\n%bad = icmp ne i32 %v, 17\n%r = zext i1 %bad to i32\nret i32 %r', 0),
    ('heap-load', allocate+'%q = getelementptr i8, ptr %p, i64 4\n%v = load i8, ptr %q', 7),
    ('heap-store', allocate+'%q = getelementptr i8, ptr %p, i64 4\nstore i8 1, ptr %q', 7),
    ('freed-load', allocate+'call void @__bennett_nz_free(ptr %p)\n%v = load i8, ptr %p', 7),
    ('freed-store', allocate+'call void @__bennett_nz_free(ptr %p)\nstore i8 1, ptr %p', 7),
    ('adjacent', allocate+'%q = call ptr @__bennett_nz_alloc(i64 4)\n%v = load i64, ptr %p', 7),
    ('zero-size', '%p = call ptr @__bennett_nz_alloc(i64 0)\n%v = load i8, ptr %p', 7),
    ('interior-free', allocate+'%q = getelementptr i8, ptr %p, i64 1\ncall void @__bennett_nz_free(ptr %q)', 7),
    ('double-free', allocate+'call void @__bennett_nz_free(ptr %p)\ncall void @__bennett_nz_free(ptr %p)', 7),
    ('global-free', 'call void @__bennett_nz_free(ptr @bytes)', 7),
    ('global-live', 'store i8 4, ptr @bytes\n%v = load i8, ptr @bytes\n%bad = icmp ne i8 %v, 4\n%r = zext i1 %bad to i32\nret i32 %r', 0),
    ('global-end', '%q = getelementptr [8 x i8], ptr @bytes, i64 0, i64 8\n%v = load i8, ptr %q', 7),
    ('memcpy-destination', allocate+'call void @llvm.memcpy.p0.p0.i64(ptr %p, ptr @bytes, i64 5, i1 false)', 7),
    ('memcpy-source', allocate+'call void @llvm.memcpy.p0.p0.i64(ptr @bytes, ptr %p, i64 5, i1 false)', 7),
    ('memmove-range', allocate+'call void @llvm.memmove.p0.p0.i64(ptr %p, ptr @bytes, i64 5, i1 false)', 7),
    ('memset-range', allocate+'call void @llvm.memset.p0.i64(ptr %p, i8 9, i64 5, i1 false)', 7),
    ('null-load', '%v = load i8, ptr null', 7),
    ('wrapping-range', 'call void @llvm.memset.p0.i64(ptr inttoptr (i64 -2 to ptr), i8 0, i64 4, i1 false)', 7),
    ('zero-copy', 'call void @llvm.memcpy.p0.p0.i64(ptr null, ptr null, i64 0, i1 false)', 0),
    ('explicit-zero', 'call void @__bennett_nz_fault(i64 0)', 4),
    ('full-code', 'call void @__bennett_nz_fault(i64 -1)', 2**64-1),
    ('libc-body', '%v = call i64 @strlen(ptr @bytes)', 23),
    ('unused-allocation', '%p = call ptr @malloc(i64 1)', 24),
]
with tempfile.TemporaryDirectory(dir=root/'.tmp',prefix='native-memory-') as temp:
    d = pathlib.Path(temp)
    for major in (18,23):
        configure(major)
        ir = d/f'device-{major}.ll'
        text = '''target triple = "x86_64-unknown-linux-gnu"
@bytes = global [8 x i8] zeroinitializer, align 8
declare ptr @__bennett_nz_alloc(i64)
declare void @__bennett_nz_free(ptr)
declare void @__bennett_nz_fault(i64)
declare void @llvm.memcpy.p0.p0.i64(ptr, ptr, i64, i1)
declare void @llvm.memmove.p0.p0.i64(ptr, ptr, i64, i1)
declare void @llvm.memset.p0.i64(ptr, i8, i64, i1)
define i64 @strlen(ptr %p) { call void @__bennett_nz_fault(i64 23)
 ret i64 0 }
define ptr @malloc(i64 %n) allocsize(0) { call void @__bennett_nz_fault(i64 24)
 ret ptr null }
define i32 @main(i32 %argc, ptr %argv) {
 switch i32 %argc, label %done [
'''
        text += ''.join(f' i32 {i+1}, label %case{i}\n' for i in range(len(cases)))+']\n'
        for i, (name, body, code) in enumerate(cases):
            # Locals have function scope in LLVM IR; keep every case's names unique.
            import re
            body = re.sub(r'%([a-z]+)',lambda m:f'%{m[1]}_{i}',body)
            text += f'case{i}:\n{body}\n'+('' if body.rstrip().endswith('i32 %r_'+str(i)) else 'ret i32 0\n')
        text += 'done:\nret i32 0\n}\n'
        ir.write_text(text)
        digest = sha(ir)
        layout = d/f'layout-{major}.json'
        layout.write_text(json.dumps(dict(null_size=4096,ptr_width=64,heap_base=69632,
            heap_limit_max=1048576,globals={},interface_regions={})))
        out = d/f'out-{major}'
        run([sys.argv[1],f'--bennett-llvm-major={major}',f'--bennett-materialised={ir}',
             f'--bennett-out={out}',f'--bennett-comparison-layout={layout}', '--bennett-layout-data-base=65536'])
        assert sha(ir) == digest
        for level in ('O0','O2'):
            for index,(name,body,code) in enumerate(cases):
                p = subprocess.run([out/f'native-{level}',*(['x']*index)],capture_output=True,timeout=5)
                expected = f'bennett runtime fault {code}\n'.encode() if code else b''
                assert (p.returncode != 0 if code else p.returncode == 0) and p.stderr == expected and not p.stdout, (major,level,name,p)
        coverage = json.loads((out/'native-detection.json').read_text())
        assert coverage['general_memory'] and coverage['use_after_free'] and coverage['out_of_live_allocation'], coverage
        assert coverage['infrastructure_exit_status'] == 125 and coverage['status'] == 'instrumented'
        receipt = json.loads((out/'manifest.json').read_text())
        stages = [c['stage'] for c in receipt['commands']]
        assert stages.index('comparison-checks') < stages.index('comparison-support-link')
        assert receipt['native_check_adapter']['sha256'] == sha(sibling('bennett-runtimes')/'scripts/native-check')
        assert receipt['checked_materialised']['sha256'] == sha(out/'comparison-checked.bc')
        # Host setup failures must not be mistaken for a dialect fault.
        def constrained(): resource.setrlimit(resource.RLIMIT_AS,(8*1024*1024,8*1024*1024))
        p = subprocess.run([out/'native-O2'],capture_output=True,timeout=5,preexec_fn=constrained)
        assert p.returncode == 125 and p.stderr.startswith(b'bennett infrastructure failure:') and b'bennett runtime fault' not in p.stderr, p
        print(f'LLVM{major}: {2*len(cases)} materialised memory/fault outcomes and infrastructure failure verified')
