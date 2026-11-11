"""The ordinary driver pipeline passes the common layout into R production."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from toolchain import configure,sibling,target_headers


def run(argv,expected=0):
    process=subprocess.Popen(list(map(str,argv)),stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
    try:
        stdout,stderr=process.communicate(timeout=180)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid,signal.SIGKILL)
        process.communicate()
        raise AssertionError('UNKNOWN: 180-second execution guard')
    result=subprocess.CompletedProcess(argv,process.returncode,stdout,stderr)
    assert result.returncode==expected,(result.returncode,result.stderr.decode())
    return result



with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'],prefix='native-process-startup-') as temp:
    directory=Path(temp)
    for major in (18,23):
        paths=configure(major)
        source=directory/f'main-{major}.c'
        source.write_text('''#include <stdio.h>
#include <stdlib.h>
typedef void (*finalizer)(void);
finalizer const __fini_array_start[1] = {0};
extern finalizer const __fini_array_end[1] __attribute__((alias("__fini_array_start")));
static void finish(void) { puts("bye"); }
int main(void) { if (atexit(finish)) return 83; fputs("tail",stdout); return 7; }
''')
        out=directory/str(major)
        run([sys.argv[1],f'--bennett-llvm-major={major}','-bennett-dialect=0.3-r1','-bennett-isa=0.9',
            '--bennett-tier=reversible','--bennett-entry=main','--bennett-comparison=true',
            '--bennett-layout-data-base=65536',f'--bennett-out={out}',
            f'--bennett-plugin={sibling("bennett-plugin-r-contract")}/build/libbennett-plugin-{major}.so',
            f'--bennett-native-provider={sibling("bennett-native-provider")}/target/debug/libbennett_vm.so',
            f'--bennett-native-target={sibling("bennett-native-targets")}/targets/ideal-all-to-all.json',
            *[f'--bennett-{key}={paths[key]}' for key in ('runtimes','arith','sysroot')],
            '-bennett-budget-default=10000000,1048576,65536,256,65536',source])
        manifest=json.loads((out/'manifest.json').read_text())
        producer=next(r for r in manifest['commands'] if r['stage']=='plugin')
        assert '-bennett-layout-data-base=65536' in producer['argv'],producer['argv']
        assert json.loads((out/'main/build.json').read_text())['layout']['globals']['G1']['base']==65536
        for level in ('O0','O2'):
            result=run([out/('native-'+level)],7)
            assert result.stdout==b'tailbye\n' and result.stderr==b'',(result.stdout,result.stderr)
            record=json.loads(Path(str(out/('native-'+level))+'.runtime.json').read_text())
            assert record['lifetime']['unload_status']==0 and record['lifetime']['binding_calls']==1,record
        print(f'LLVM{major}: full R driver pipeline common layout, process cleanup, live program binding, return7 at O0/O2')
