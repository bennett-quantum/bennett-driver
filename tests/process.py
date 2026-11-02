"""Process-entry component checks; native diagnostics do not establish R acceptance."""
import hashlib, json, os, pathlib, re, subprocess, sys, tempfile
from contextlib import nullcontext

root=pathlib.Path(__file__).resolve().parents[1]
ws=root.parent
exe=pathlib.Path(sys.argv[1]).resolve()
def run(args, **kwargs):
    p=subprocess.run(list(map(str,args)),capture_output=True,timeout=120,**kwargs)
    assert p.returncode==0,p.stderr.decode()
    return p.stdout
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

source='''#include <errno.h>
extern char **environ;
extern char *program_invocation_name, *program_invocation_short_name;
extern unsigned __bennett_rt_fenv[2];
int program(int argc,char **argv,char **envp) {
 if (!argv || !envp || environ!=envp || errno || __bennett_rt_fenv[0] || __bennett_rt_fenv[1]) return 11;
 if (argv[argc]) return 12;
 if (!argc) return argv[0] || envp[0] || *program_invocation_name || *program_invocation_short_name;
 if (argc!=3 || argv[1][0]!='A' || argv[1][1] || argv[2][0]!='B' || argv[2][1]!='C' || argv[2][2]) return 13;
 char *name=argv[0],*base=name;
 for (char *p=name; *p; ++p) if (*p=='/') base=p+1;
 if (program_invocation_name!=name || program_invocation_short_name!=base) return 14;
 return 0;
}
'''
evidence=os.environ.get('BENNETT_DRIVER_PROCESS_EVIDENCE')
if evidence: pathlib.Path(evidence).mkdir(parents=True,exist_ok=False)
with (nullcontext(evidence) if evidence else tempfile.TemporaryDirectory(dir=root/'.tmp',prefix='process-')) as temp:
    d=pathlib.Path(temp)
    for major in (18,23):
        llvm=pathlib.Path(f'/usr/lib/llvm-{major}/bin')
        sysroot=ws/f'bennett-runtimes/dist/llvm{major}/musl-sysroot'
        c=d/f'program-{major}.c';c.write_text(source)
        out=d/f'production-{major}'
        command=[exe,f'--bennett-llvm-major={major}','-bennett-dialect=0.2.10',
            '--bennett-tier=reversible','--bennett-entry=program',f'--bennett-out={out}',
            '--bennett-emit=process-bitcode',
            f'--bennett-sysroot={sysroot}','--bennett-analysis-budget-ms=300000',
            '-bennett-budget-default=10000000,1048576,65536,256,65536',c]
        p=subprocess.run(['timeout','180',*map(str,command)],capture_output=True,timeout=190)
        assert p.returncode==0,p.stderr.decode()
        manifest=json.loads((out/'manifest.json').read_text())
        assert 'process_preparation' in manifest, p.stderr.decode()
        prepared=out/'process-prepared.bc'
        assert manifest['process_preparation']['module']['sha256']==sha(prepared)
        stages=[x['stage'] for x in manifest['commands']]
        assert stages.index('process-entry') < stages.index('process-root-audit'), stages
        assert manifest['status']=='prepared' and not (out/'launches.json').exists()
        assert not any(stage in stages for stage in ('postlink','plugin'))
        report=json.loads((out/'process-entry.json').read_text())
        ir=run([llvm/'llvm-dis',out/'process-entry.bc','-o','-']).decode()
        body=ir.split('define i32 @program(',1)[1].split('\n}',1)[0]
        assert body.index('@__bennett_rt_prepare_process(')<body.index('@'+report['user_entry']+'(')
        assert '@exit(' in body and 'unreachable' in body
        linked=run([llvm/'llvm-dis',prepared,'-o','-']).decode()
        assert re.search(r'^define .*@__bennett_rt_prepare_process\(',linked,re.M), 'helper must be defined before S2/S7'
        assert 'global { i32, i32 } zeroinitializer' in linked, 'fresh shared fenv image'
        print(f'LLVM{major}: explicit preparation stage emitted; full R acceptance remains separate')
        # Inspect this driver's pre-materialisation stage with the real native
        # runtime. This is an isolated entry-preparation diagnostic, not a
        # substitute for the plugin's actual materialised comparison module.
        layout=d/f'layout-{major}.json'
        # The retained O0/O2 maps end at 0x10a38/0x10a18; the first page is
        # 0x11000. The driver's equality assertion remains mandatory.
        layout.write_text(json.dumps(dict(null_size=4096,ptr_width=64,heap_base=69632,
            heap_limit_max=1048576,globals={},interface_regions={})))
        for name,call in [('supplied','program(argc,argv,envp)'),('empty','program(0,0,0)')]:
            harness=d/f'{name}-{major}.c'
            harness.write_text('''#include <errno.h>
extern unsigned __bennett_rt_fenv[2];
extern int program(int,char **,char **);
int main(int argc,char **argv,char **envp) {
 errno=123; __bennett_rt_fenv[0]=4; __bennett_rt_fenv[1]=31;
 return '''+call+''';
}
''')
            native=d/f'{name}-native-{major}'
            run([exe,f'--bennett-llvm-major={major}',f'--bennett-materialised={prepared}',
                f'--bennett-native-input={harness}',f'--bennett-out={native}',
                f'--bennett-comparison-layout={layout}','--bennett-layout-data-base=65536'])
            for level in ('O0','O2'):
                for repeat in range(2):
                    assert run([native/f'native-{level}','A','BC'])==b''
            record=json.loads((native/'manifest.json').read_text())
            assert record['native_check_adapter'] and record['checked_materialised']
        print(f'LLVM{major}: supplied/empty vectors, errno/fenv reset, aliases and fresh native images verified')
