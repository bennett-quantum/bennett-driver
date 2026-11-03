"""Configured register classes must be consumed by real production lowering."""
import hashlib, json, os, pathlib, subprocess, sys, tempfile
from toolchain import flags, target_headers
from contextlib import nullcontext
root=pathlib.Path(__file__).resolve().parents[1]
plugin_root=pathlib.Path(os.environ.get('BENNETT_DRIVER_MODERN_PLUGIN_ROOT') or root.parent/'bennett-plugin')
def run(args):
    p=subprocess.run(list(map(str,args)),capture_output=True,timeout=120)
    assert p.returncode==0,p.stderr.decode()
    return p.stdout
evidence=os.environ.get('BENNETT_DRIVER_CLASS_EVIDENCE')
if evidence:pathlib.Path(evidence).mkdir(parents=True,exist_ok=False)
with (nullcontext(evidence) if evidence else tempfile.TemporaryDirectory(dir=root/'.tmp',prefix='configured-classes-')) as temp:
    d=pathlib.Path(temp)
    for m in (18,23):
        plugin=plugin_root/f'build/libbennett-plugin-{m}.so'
        base=[sys.argv[1],*flags(m,plugin=False),f'--bennett-plugin={plugin}',
              '--bennett-plugin-sha256='+hashlib.sha256(plugin.read_bytes()).hexdigest(),
              '--bennett-dialect=0.2.13',f'--bennett-llvm-major={m}']
        source=d/f'scalable-{m}.ll'
        source.write_text(target_headers(m)+'''declare ptr @__bennett_qalloc(i64,i64)
declare void @__bennett_qfree(ptr)
declare i64 @llvm.vscale.i64()
define i64 @top() {
 %q=call ptr @__bennett_qalloc(i64 1,i64 1)
 call void @__bennett_qfree(ptr %q)
 %v=call i64 @llvm.vscale.i64()
 ret i64 %v
}
!llvm.module.flags = !{!0}
!0 = !{i32 6, !"bennett.classes", !1}
!1 = !{!"alpha"}
''')
        out=d/f'device-{m}'
        run([*base,f'--bennett-out={out}','--bennett-vscale=2','--bennett-class=alpha',
             '--bennett-class=beta','--bennett-class=alpha',source])
        report=json.loads((out/'mode-preparation.json').read_text())
        assert report['classes']==['alpha','beta'] and report['vscale']==2,report
        post=run([f'/usr/lib/llvm-{m}/bin/llvm-dis',out/'postlink.bc','-o','-']).decode()
        assert 'call i64 @llvm.vscale' not in post and 'ret i64 2' in post
        assert 'alpha' in (out/'top/launch.bennett').read_text()
        build=json.loads((out/'build.json').read_text())
        stages=[c['stage'] for c in build['commands']]
        assert stages.index('mode-preparation')<stages.index('postlink')<stages.index('plugin')
    print('Both majors: configured alpha register class is lowered into the actual ISA object')
