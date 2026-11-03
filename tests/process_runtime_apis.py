"""Retain localeconv/getpagesize checks independently of driver preparation.

The private state profile exists, but the public APIs are a separate runtime
publication obligation. This test must remain red while either API is absent.
"""
import json, pathlib, subprocess, sys, tempfile
from toolchain import flags
root=pathlib.Path(__file__).resolve().parents[1]
ws=root.parent
def run(args):
    p=subprocess.run(list(map(str,args)),capture_output=True,timeout=120)
    assert p.returncode==0,p.stderr.decode()
    return p.stdout
missing={}
for major in (18,23):
    llvm=pathlib.Path(f'/usr/lib/llvm-{major}/bin')
    symbols={line.split()[-1] for line in run([llvm/'llvm-nm','--defined-only',ws/f'bennett-runtimes/dist/llvm{major}/bennett-runtimes.bc']).decode().splitlines() if line.split()}
    absent=sorted({'getpagesize','localeconv'}-symbols)
    if absent: missing[major]=absent
assert not missing, f'Published process-state API definitions are required: {missing}'
with tempfile.TemporaryDirectory(dir=root/'.tmp',prefix='process-apis-') as temp:
    d=pathlib.Path(temp)
    for major in (18,23):
        source=d/f'apis-{major}.c'
        source.write_text('''#include <locale.h>
#include <unistd.h>
int main(void) {
 struct lconv *p=localeconv();
 return getpagesize()!=4096 || !p || p->decimal_point[0]!='.' || p->decimal_point[1];
}
''')
        prepared=d/f'prepared-{major}'
        run([sys.argv[1],*flags(major),f'--bennett-llvm-major={major}','-bennett-dialect=0.2.10',
            '--bennett-tier=reversible','--bennett-entry=main','--bennett-emit=process-bitcode',
            f'--bennett-out={prepared}',f'--bennett-sysroot={ws}/bennett-runtimes/dist/llvm{major}/musl-sysroot',source])
        # Fixed-IR codegen maps end at 0x11020 (18) and 0x11050 (23);
        # the first following page is 0x12000. Keep the exact assertion.
        layout=d/f'layout-{major}.json'
        layout.write_text(json.dumps(dict(null_size=4096,ptr_width=64,heap_base=73728,
            heap_limit_max=1048576,globals={},interface_regions={})))
        out=d/f'native-{major}'
        run([sys.argv[1],f'--bennett-llvm-major={major}',f'--bennett-materialised={prepared/"process-prepared.bc"}',
            f'--bennett-out={out}',f'--bennett-comparison-layout={layout}','--bennett-layout-data-base=65536'])
        for level in ('O0','O2'): assert run([out/f'native-{level}'])==b''
