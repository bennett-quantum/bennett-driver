import os, json, pathlib, subprocess, sys, tempfile
from toolchain import flags, target_headers
root=pathlib.Path(__file__).resolve().parents[1]
ws=root.parent
with tempfile.TemporaryDirectory(dir=root/'.tmp',prefix='reports-') as temp:
    for label,extra,inputs in [
        ('version',['-bennett-dialect=wrong'],['no.bc']),
        ('unsupported',[],['source.rs']),
        ('unknown',['--not-real=true'],['no.bc']),
        ('flag',[],[]),
        ('mixed',[],[]),
        ('pin',['--bennett-arith-sha256='+'0'*64],['no.bc']),
        ('identity',[],['no.bc']),
        ('newer',[],[]),
        ('marker',[],[]),
        ('native-marker',[],[]),
    ]:
        out=pathlib.Path(temp)/label
        if label=='identity':
            src=pathlib.Path(temp)/'identity.c'
            src.write_text('struct Info { unsigned api; const char *name,*version; void *callback,*codegen; }; struct Info llvmGetPassPluginInfo(void) { return (struct Info){2,"bennett","dialect-wrong",0,0}; }')
            plugin=pathlib.Path(temp)/'identity.so'
            subprocess.run(['/usr/lib/llvm-23/bin/clang','-shared','-fPIC',str(src),'-o',str(plugin)],check=True)
            extra=['--bennett-plugin='+str(plugin)]
        if label=='newer':
            src=pathlib.Path(temp)/'newer.ll'
            # A post-18 attribute that stock LLVM18 cannot parse.
            src.write_text('define noundef range(i32 0, 10) i32 @f() {ret i32 0}\n')
            inputs=[str(src)];extra=['--bennett-llvm-major=18']
        if label in ('marker','native-marker'):
            src=pathlib.Path(temp)/'marker.ll'
            src.write_text(target_headers(23)+'define ptr @__bennett_qalloc(i64 %c,i64 %n) { ret ptr null }\ndefine void @top() { %q = call ptr @__bennett_qalloc(i64 0,i64 1)\n ret void }\n')
            inputs=[str(src)]
            if label=='native-marker':
                bc=pathlib.Path(temp)/'native-marker.bc'
                subprocess.run(['/usr/lib/llvm-23/bin/llvm-as',str(src),'-o',str(bc)],check=True)
                inputs=[];extra=['--bennett-materialised='+str(bc)]
        if label=='flag':
            f=pathlib.Path(temp)/'flag.ll'
            f.write_text(target_headers(23)+'define i32 @f() { ret i32 0 }\n!llvm.module.flags = !{!0}\n!0 = !{i32 1, !"bennett.dialect", !"0.1"}\n')
            inputs=[str(f)]
        if label=='mixed':
            inputs=[]
            for n,t in enumerate(('x86_64-unknown-linux-gnu','aarch64-unknown-linux-gnu')):
                f=pathlib.Path(temp)/f'mixed{n}.ll'
                f.write_text('\n'.join(line for line in target_headers(23).splitlines() if not line.startswith('target triple'))+f'\ntarget triple = "{t}"\ndefine i32 @f{n}() {{ret i32 0}}\n')
                inputs.append(str(f))
        keys={a.split('=',1)[0] for a in extra}
        extra += [a for a in flags(18 if label=='newer' else 23, plugin=label!='identity') if a.split('=',1)[0] not in keys]
        p=subprocess.run([sys.argv[1],*(['-bennett-dialect=0.2.10'] if label!='version' else []),f'-bennett-out={out}',*extra,*inputs],capture_output=True)
        assert p.returncode!=0
        path=out/'blockers.json'
        assert path.is_file(),f'{label}: no report: {p.stderr.decode()}'
        r=json.loads(path.read_text());assert isinstance(r,list) and r
        assert all(set(('code','reason','stage','constraint','required_change','diagnostic')) <= x.keys() for x in r),r
        if label in ('version','flag','mixed','pin','identity','newer'):
            assert r[0]['code']=='BD-E-VERSION',r
        if label in ('marker','native-marker'):
            assert r[0]['code']=='BD-E-MARKER-DEFINED',r
        assert (out/'blockers.txt').is_file()
        print(label,r[0]['code'])
