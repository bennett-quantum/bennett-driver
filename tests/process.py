"""Process-entry component checks; native diagnostics do not establish R acceptance."""
import hashlib, json, os, pathlib, re, subprocess, sys, tempfile
from contextlib import nullcontext
from toolchain import flags

root=pathlib.Path(__file__).resolve().parents[1]
ws=root.parent
exe=pathlib.Path(sys.argv[1]).resolve()
def run(args, **kwargs):
    p=subprocess.run(list(map(str,args)),capture_output=True,timeout=120,**kwargs)
    assert p.returncode==0,f'{args}: exit {p.returncode}\n{p.stdout!r}\n{p.stderr.decode()}'
    return p.stdout
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

source='''#include <errno.h>
#include <stdlib.h>
#include <pthread.h>
extern char **environ;
extern char *program_invocation_name, *program_invocation_short_name;
extern unsigned __bennett_rt_fenv[2];
extern unsigned long __bennett_dev_console_n, __bennett_dev_console_L;
extern unsigned __bennett_dev_console_bound, __bennett_dev_console_action;
extern unsigned char *__bennett_dev_console_buffer;
int program(int argc,char **argv,char **envp) {
 if (!argv || !envp || environ!=envp || errno || __bennett_rt_fenv[0] || __bennett_rt_fenv[1]) return 11;
 if (!pthread_self()) return 16;
 if (__bennett_dev_console_n!=3 || __bennett_dev_console_L!=16 || !__bennett_dev_console_bound || !__bennett_dev_console_action || __bennett_dev_console_buffer[0]!=9) return 17;
 if (argv[argc]) return 12;
 if (!argc) return argv[0] || envp[0] || *program_invocation_name || *program_invocation_short_name;
 if (argc!=3 || argv[1][0]!='A' || argv[1][1] || argv[2][0]!='B' || argv[2][1]!='C' || argv[2][2]) return 13;
 char *name=argv[0],*base=name;
 for (char *p=name; *p; ++p) if (*p=='/') base=p+1;
 if (program_invocation_name!=name || program_invocation_short_name!=base) return 14;
 char *value=getenv("BENNETT_PROCESS_BYTES");
 if (!value || value[0]!='o' || value[1]!='k' || value[2]) return 15;
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
        command=[exe,*flags(major),f'--bennett-llvm-major={major}','-bennett-dialect=0.2.10',
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
        run([manifest['process_preparation']['tool']['path'],'--verify',prepared,'program'])
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
        definitions={line.split()[-1] for line in run([llvm/'llvm-nm','--defined-only',prepared]).decode().splitlines() if line.split()}
        assert not definitions.intersection({'__bennett_nz_alloc','__bennett_nz_free','__bennett_nz_fault','_start'}), 'native-only support entered production preparation'
        print(f'LLVM{major}: explicit preparation stage emitted; full R acceptance remains separate')
        # Missing or differently typed preparation cannot silently fall back to
        # an unprepared process, even when llvm-link accepts opaque pointers.
        missing=d/f'missing-runtime-{major}.bc'
        run([llvm/'llvm-extract','--delete','--func=__bennett_rt_prepare_process',
            ws/f'bennett-runtimes/dist/llvm{major}/bennett-runtimes.bc','-o',missing])
        wrong_ir=d/f'wrong-helper-{major}.ll'
        wrong_ir.write_text('define void @__bennett_rt_prepare_process(i64 %argc, ptr %argv, ptr %envp) { ret void }\n')
        wrong_bc=d/f'wrong-helper-{major}.bc'
        run([llvm/'llvm-as',wrong_ir,'-o',wrong_bc])
        wrong=d/f'wrong-runtime-{major}.bc'
        run([llvm/'llvm-link',missing,wrong_bc,'-o',wrong])
        for label,runtime in [('missing',missing),('wrong-type',wrong)]:
            refused=d/f'{label}-{major}'
            args=[f'--bennett-out={refused}' if str(x).startswith('--bennett-out=') else str(x)
                for x in command if not str(x).startswith(('--bennett-runtimes=', '--bennett-runtimes-sha256='))]
            args.insert(1,f'--bennett-runtimes={runtime}')
            p=subprocess.run(['timeout','120',*args],capture_output=True,timeout=130)
            assert p.returncode and b'BD-E-PROCESS' in p.stderr and b'__bennett_rt_prepare_process' in p.stderr,(label,p.stderr)
            assert not (refused/'process-prepared.bc').exists()
        # Inspect this driver's pre-materialisation stage with the real native
        # runtime. This is an isolated entry-preparation diagnostic, not a
        # substitute for the plugin's actual materialised comparison module.
        layout=d/f'layout-{major}.json'
        # The fixed-IR codegen maps are retained in the process evidence.
        # Use their first following page, 0x12000; exact equality stays mandatory.
        layout.write_text(json.dumps(dict(null_size=4096,ptr_width=64,heap_base=73728,
            heap_limit_max=1048576,globals={},interface_regions={})))
        for name,call in [('supplied','program(argc,argv,envp)'),('empty','program(0,0,0)')]:
            harness=d/f'{name}-{major}.c'
            harness.write_text('''#include <errno.h>
extern unsigned __bennett_rt_fenv[2];
extern int program(int,char **,char **);
extern char **environ;
extern char *program_invocation_name, *program_invocation_short_name;
extern unsigned long __bennett_dev_console_n, __bennett_dev_console_L;
extern unsigned __bennett_dev_console_bound, __bennett_dev_console_action;
extern unsigned char *__bennett_dev_console_buffer;
static unsigned char buffer[16]={9};
int main(int argc,char **argv,char **envp) {
 char *empty[1]={0}; environ=empty;
 program_invocation_name="stale"; program_invocation_short_name="stale";
 errno=123; __bennett_rt_fenv[0]=4; __bennett_rt_fenv[1]=31;
 __bennett_dev_console_n=3; __bennett_dev_console_L=16;
 __bennett_dev_console_bound=1; __bennett_dev_console_action=1; __bennett_dev_console_buffer=buffer;
 return '''+call+''';
}
''')
            native=d/f'{name}-native-{major}'
            run([exe,f'--bennett-llvm-major={major}',f'--bennett-materialised={prepared}',
                f'--bennett-native-input={harness}',f'--bennett-out={native}',
                f'--bennett-comparison-layout={layout}','--bennett-layout-data-base=65536'])
            for level in ('O0','O2'):
                for repeat in range(2):
                    for display in ('demo','/usr/local/bin/demo','/tmp/trailing/',''):
                        assert run([display,'A','BC'],executable=native/f'native-{level}',env=dict(os.environ,BENNETT_PROCESS_BYTES='ok'))==b''
            record=json.loads((native/'manifest.json').read_text())
            assert record['native_check_adapter'] and record['checked_materialised']
            native_ir=run([llvm/'llvm-dis',native/'comparison.bc','-o','-']).decode()
            functions=re.findall(r'^define [^\n]*\{\n.*?^\}',native_ir,re.M|re.S)
            startup=[body for body in functions if '@__bennett_rt_native_inputs(' in body and '@__bennett_rt_prepare_process(' in body]
            assert startup and all(body.index('@__bennett_rt_native_inputs(')<body.index('@__bennett_rt_prepare_process(') for body in startup)
            checked_prepare=[body for body in functions if re.match(r'define [^\n]*@__bennett_rt_prepare_process\(',body)]
            assert checked_prepare and '@__bennett_rt_native_check(' in checked_prepare[0]
        print(f'LLVM{major}: supplied/empty vectors, errno/fenv reset, aliases and fresh native images verified')
        # The two-parameter C main form still receives the same prepared envp
        # through public environ while forwarding exactly its original ABI.
        two_source=d/f'two-{major}.c'
        two_source.write_text(source.replace('int program(int argc,char **argv,char **envp) {',
            'int program(int argc,char **argv) { char **envp=environ;'))
        two_prepared=d/f'two-prepared-{major}'
        two_args=[str(x) for x in command]
        two_args=[f'--bennett-out={two_prepared}' if x.startswith('--bennett-out=') else str(two_source) if x==str(c) else x for x in two_args]
        run(two_args)
        assert json.loads((two_prepared/'process-entry.json').read_text())['user_parameters']==2
        two_out=d/f'two-native-{major}'
        run([exe,f'--bennett-llvm-major={major}',f'--bennett-materialised={two_prepared/"process-prepared.bc"}',
            f'--bennett-native-input={d/f"supplied-{major}.c"}',f'--bennett-out={two_out}',
            f'--bennett-comparison-layout={layout}','--bennett-layout-data-base=65536'])
        for level in ('O0','O2'):
            assert run([two_out/f'native-{level}','A','BC'],env=dict(os.environ,BENNETT_PROCESS_BYTES='ok'))==b''
        bad=d/f'bad-{major}.c'
        bad.write_text('''extern int program(int,char **,char **);
extern void *__bennett_nz_alloc(unsigned long);
int main(int argc,char **argv,char **envp) {
 char *empty[1]={0};
 if (argv[1][0]=='n') return program(-1,0,0);
 if (argv[1][0]=='p') return program(1,0,0);
 if (argv[1][0]=='a') { char *v[3]={"p",0,0}; return program(2,v,empty); }
 if (argv[1][0]=='t') { char *v[2]={"p","extra"}; return program(1,v,empty); }
 if (argv[1][0]=='s') { char *p=__bennett_nz_alloc(1); p[0]='p'; char *v[2]={p,0}; return program(1,v,empty); }
 char **v=__bennett_nz_alloc(sizeof(char *)); v[0]="E=x"; return program(0,empty,v);
}
''')
        bad_out=d/f'bad-native-{major}'
        run([exe,f'--bennett-llvm-major={major}',f'--bennett-materialised={prepared}',
            f'--bennett-native-input={bad}',f'--bennett-out={bad_out}',
            f'--bennett-comparison-layout={layout}','--bennett-layout-data-base=65536'])
        for level in ('O0','O2'):
            for case in ('negative','positive-null','arg-null','terminator','string','env-terminator'):
                p=subprocess.run([bad_out/f'native-{level}',case],capture_output=True,timeout=10)
                assert p.returncode and not p.stdout and p.stderr==b'bennett runtime fault 7\n',(major,level,case,p)
        print(f'LLVM{major}: invalid count/vector/string inputs fault7 before entry')
        # Zero-parameter C main form: normal return must terminate through exit,
        # before the harness can emit AFTER; explicit exit is the same path,
        # while _Exit omits handlers and the buffered text.
        exit_source=d/f'exit-{major}.c'
        exit_source.write_text('''#include <stdlib.h>
#include <stdio.h>
static void first(void) { fputs("first",stdout); }
static void second(void) { fputs("second",stdout); }
int program(void) {
 atexit(first); atexit(second); fputs("body",stdout);
 char mode=getenv("BENNETT_PROCESS_MODE")[0];
 if (mode=='x') exit(0);
 if (mode=='q') _Exit(0);
 return 0;
}
''')
        exit_prepared=d/f'exit-prepared-{major}'
        exit_args=[str(x) for x in command]
        exit_args=[f'--bennett-out={exit_prepared}' if x.startswith('--bennett-out=') else str(exit_source) if x==str(c) else x for x in exit_args]
        run(exit_args)
        assert json.loads((exit_prepared/'process-entry.json').read_text())['user_parameters']==0
        exit_harness=d/f'exit-harness-{major}.c'
        exit_harness.write_text('''#include <unistd.h>
extern int program(int,char **,char **);
int main(int argc,char **argv,char **envp) { program(argc,argv,envp); write(1,"AFTER",5); return 42; }
''')
        exit_layout=d/f'exit-layout-{major}.json'
        # Exit/stdio uses its measured fixed-IR codegen page; exact equality is checked.
        exit_layout.write_text(json.dumps(dict(null_size=4096,ptr_width=64,heap_base=73728,
            heap_limit_max=1048576,globals={},interface_regions={})))
        exit_out=d/f'exit-native-{major}'
        run([exe,f'--bennett-llvm-major={major}',f'--bennett-materialised={exit_prepared/"process-prepared.bc"}',
            f'--bennett-native-input={exit_harness}',f'--bennett-out={exit_out}',
            f'--bennett-comparison-layout={exit_layout}','--bennett-layout-data-base=65536'])
        for level in ('O0','O2'):
            for mode,expected in (('r',b'bodysecondfirst'),('x',b'bodysecondfirst'),('q',b'')):
                assert run([exit_out/f'native-{level}'],env=dict(os.environ,BENNETT_PROCESS_MODE=mode))==expected,(major,level,mode)
        print(f'LLVM{major}: return/exit LIFO and exactly-once flush; _Exit omission verified')
