"""Every external child retains the caller's task TMPDIR and stays headless."""
import os, pathlib, subprocess, sys, tempfile
from toolchain import flags
root = pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(dir=root/'.tmp', prefix='environment-') as temp:
    d = pathlib.Path(temp)
    child = d/'children'
    child.mkdir()
    capture = d/'captured.txt'
    source = d/'identity.c'
    source.write_text('''#include <stdio.h>
#include <stdlib.h>
struct Info {unsigned api; const char *name,*version; void *callback,*codegen;};
struct Info llvmGetPassPluginInfo(void) {
 FILE *out=fopen(getenv("BENNETT_TEST_ENV_CAPTURE"),"w");
 fprintf(out,"%s\\n%d%d%d%d\\n",getenv("TMPDIR"),getenv("DISPLAY")!=0,
  getenv("WAYLAND_DISPLAY")!=0,getenv("DBUS_SESSION_BUS_ADDRESS")!=0,getenv("BROWSER")!=0);
 fclose(out);
 return (struct Info){2,"bennett","dialect-0.2.10;isa-0.8",0,0};
}
''')
    plugin = d/'identity.so'
    subprocess.run(['/usr/lib/llvm-23/bin/clang','-shared','-fPIC',source,'-o',plugin],capture_output=True,check=True)
    ir = d/'untyped.ll'
    ir.write_text('define i32 @main() {ret i32 0}\n')
    env = dict(os.environ, TMPDIR=str(child), BENNETT_TEST_ENV_CAPTURE=str(capture))
    env.update({key:'must-be-removed' for key in ('DISPLAY','WAYLAND_DISPLAY','DBUS_SESSION_BUS_ADDRESS','BROWSER')})
    result = subprocess.run([sys.argv[1],*flags(23, plugin=False),'-bennett-dialect=0.2.10',
        f'--bennett-plugin={plugin}',f'--bennett-out={d}/out',str(ir)],capture_output=True,env=env,timeout=30)
    assert result.returncode and b'missing target ' in result.stderr,result.stderr
    assert capture.read_text().splitlines() == [str(child),'0000'],capture.read_text()
