import os,json,pathlib,subprocess,sys,tempfile
from toolchain import flags, target_headers
root=pathlib.Path(__file__).resolve().parents[1]
def run(args):
    p=subprocess.run(list(map(str,args)),capture_output=True)
    assert p.returncode==0,p.stderr.decode()
    return p.stdout
with tempfile.TemporaryDirectory(dir=root/'.tmp',prefix='inputs-') as temp:
    d=pathlib.Path(temp)
    header=target_headers(23)
    a=d/'a.ll';b=d/'b.ll'
    a.write_text(header+'''declare ptr @__bennett_qalloc(i64, i64)
declare void @__bennett_qfree(ptr)
declare i64 @helper(i64)
define i64 @top(i64 %x) {
  %q = call ptr @__bennett_qalloc(i64 0, i64 1)
  call void @__bennett_qfree(ptr %q)
  %y = call i64 @helper(i64 %x)
  ret i64 %y
}
''')
    b.write_text(header+'define i64 @helper(i64 %x) { %y = add i64 %x, 1\n ret i64 %y }\n')
    run(['/usr/lib/llvm-18/bin/llvm-as',a,'-o',d/'a.bc'])
    run(['/usr/lib/llvm-23/bin/llvm-as',b,'-o',d/'b.bc'])
    for ext in ('ll','bc'):
        out=d/ext
        run([sys.argv[1],*flags(23),'-bennett-dialect=0.2.10',f'-bennett-out={out}',d/f'a.{ext}',d/f'b.{ext}'])
        assert json.loads((out/'manifest.json').read_text())['llvm_major']==23
        assert any(x['entry']=='top' for x in json.loads((out/'launches.json').read_text()))
    assert (d/'ll/top/launch.bennett').read_bytes()==(d/'bc/top/launch.bennett').read_bytes()
