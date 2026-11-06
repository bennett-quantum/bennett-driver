"""A byval argument is a live callee-local object, not an invalid pointer."""
from toolchain import configure, sibling
import hashlib, json, pathlib, subprocess, sys, tempfile

root=pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(dir=root/'.tmp',prefix='native-byval-') as temp:
    d=pathlib.Path(temp)
    ir=d/'device.ll'
    ir.write_text('''target triple = "x86_64-unknown-linux-gnu"
%S = type { i64, i64, i64 }
define i32 @read_value(ptr byval(%S) align 8 %x) noinline {
 %p = getelementptr %S, ptr %x, i32 0, i32 0
 %v = load i64, ptr %p, align 8
 %bad = icmp ne i64 %v, 17
 %r = zext i1 %bad to i32
 ret i32 %r
}
define i32 @main() {
 %s = alloca %S, align 8
 store %S { i64 17, i64 18, i64 19 }, ptr %s
 %r = call i32 @read_value(ptr byval(%S) align 8 %s)
 ret i32 %r
}
''')
    digest=hashlib.sha256(ir.read_bytes()).hexdigest()
    layout=d/'layout.json'
    layout.write_text(json.dumps(dict(null_size=4096,ptr_width=64,heap_base=69632,
        heap_limit_max=1048576,globals={},interface_regions={})))
    failures=[]
    for major in (18,23):
        configure(major)
        out=d/f'out-{major}'
        p=subprocess.run([sys.argv[1],f'--bennett-llvm-major={major}',
            f'--bennett-materialised={ir}',f'--bennett-out={out}',
            f'--bennett-comparison-layout={layout}','--bennett-layout-data-base=65536'],
            capture_output=True,timeout=120)
        assert p.returncode==0,p.stderr.decode()
        for level in ('O0','O2'):
            p=subprocess.run([out/f'native-{level}'],capture_output=True,timeout=5)
            if p.returncode or p.stdout or p.stderr:
                failures.append((major,level,p.returncode,p.stdout,p.stderr))
    assert hashlib.sha256(ir.read_bytes()).hexdigest()==digest
    assert not failures, f'Valid LLVM byval copies must return success on both majors: {failures}'
