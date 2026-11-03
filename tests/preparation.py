"""Driver transforms take effect before LTO and retain original source bytes."""
import hashlib, json, os, pathlib, subprocess, sys, tempfile
from toolchain import flags, target_headers
root=pathlib.Path(__file__).resolve().parents[1]
plugin_root=pathlib.Path(os.environ.get('BENNETT_DRIVER_MODERN_PLUGIN_ROOT') or root.parent/'bennett-plugin')
def run(args):
    p=subprocess.run(list(map(str,args)),capture_output=True,timeout=120)
    assert p.returncode==0,p.stderr.decode()
    return p.stdout
with tempfile.TemporaryDirectory(dir=root/'.tmp',prefix='preparation-') as temp:
    d=pathlib.Path(temp)
    for m in (18,23):
        plugin=plugin_root/f'build/libbennett-plugin-{m}.so'
        base=[sys.argv[1],*flags(m,plugin=False),f'--bennett-plugin={plugin}',
              '--bennett-plugin-sha256='+hashlib.sha256(plugin.read_bytes()).hexdigest(),
              '--bennett-dialect=0.2.13',f'--bennett-llvm-major={m}']
        source=d/f'native-{m}.ll'
        original=target_headers(m)+'''@g = global i8 0, align 1
define i32 @main() { %v=load i8,ptr @g
 %n=zext i8 %v to i32
 ret i32 %n }
'''
        source.write_text(original)
        snapshot=d/f'snapshot-{m}.json'
        snapshot.write_text(json.dumps({'schema':'bennett-driver-snapshot-1','globals':{'g':'07'}}))
        out=d/f'native-{m}'
        run([*base,f'--bennett-out={out}',f'--bennett-snapshot={snapshot}',source])
        assert subprocess.run([out/'native-host'],timeout=10).returncode==7
        assert source.read_text()==original
        build=json.loads((out/'build.json').read_text())
        assert build['snapshot_sha256']==hashlib.sha256(snapshot.read_bytes()).hexdigest()
        assert build['completion']=='native-only' and not build['plugin_builds']
        for label,values in [('unknown',{'absent':'07'}),('extent',{'g':'0700'})]:
            snapshot.write_text(json.dumps({'schema':'bennett-driver-snapshot-1','globals':values}))
            refused=d/f'{m}-{label}'
            p=subprocess.run([*base,f'--bennett-out={refused}',f'--bennett-snapshot={snapshot}',str(source)],capture_output=True,timeout=120)
            assert p.returncode and b'BD-E-PREPARATION' in p.stderr,p.stderr
            assert not (refused/'host.bc').exists()
        source=d/f'scalable-{m}.ll'
        source.write_text(target_headers(m)+'''declare ptr @__bennett_qalloc(i64,i64)
declare void @__bennett_qfree(ptr)
declare i64 @llvm.vscale.i64()
define i64 @top() {
 %q=call ptr @__bennett_qalloc(i64 0,i64 1)
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
        build=json.loads((out/'build.json').read_text())
        stages=[c['stage'] for c in build['commands']]
        assert stages.index('mode-preparation')<stages.index('postlink')<stages.index('plugin')
    print('Both majors: exact snapshot native value7, bad images rejected, ordered unique classes and fixed vscale2 before LTO')
