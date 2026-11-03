"""Unmarked modules retain the ordinary native process and libc."""
import hashlib, json, pathlib, subprocess, sys, tempfile
from toolchain import flags, target_headers

root = pathlib.Path(__file__).resolve().parents[1]
def run(argv, **kwargs):
    return subprocess.run(list(map(str, argv)), capture_output=True, timeout=90, **kwargs)
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

with tempfile.TemporaryDirectory(dir=root/'.tmp', prefix='native-host-') as temp:
    d = pathlib.Path(temp)
    main = d/'main.c'
    helper = d/'helper.c'
    main.write_text('''#include <stdio.h>
extern int helper(int);
int main(int argc, char **argv) {
  printf("native %s %d\\n", argv[1], helper(argc));
  return helper(argc) - 40;
}
''')
    helper.write_text('int helper(int n) { return n + 40; }\n')
    original = {str(p): sha(p) for p in (main, helper)}
    for major in (18, 23):
        out = d/f'host-{major}'
        args = [sys.argv[1], *flags(major), f'--bennett-llvm-major={major}',
                '-bennett-dialect=0.2.10', f'--bennett-out={out}']
        result = run([*args, main, helper])
        assert result.returncode == 0, result.stderr.decode()
        build = json.loads((out/'build.json').read_text())
        assert build['status'] == 'complete'
        assert build['completion'] == 'native-only'
        assert json.loads((out/'launches.json').read_text()) == []
        for inventory in ('plugin_builds', 'layouts', 'budget_tables'):
            assert build[inventory] == {}, (inventory, build[inventory])
        host = build['outputs']['native_host']
        executable = pathlib.Path(host['path'])
        assert sha(executable) == host['sha256']
        observed = run([executable, 'argument'])
        assert (observed.returncode, observed.stdout, observed.stderr) == (2, b'native argument 42\n', b''), observed
        source_link = next(c for c in build['commands'] if c['stage'] == 'native-host-link-inputs')
        assert not any('bennett-runtimes.bc' in a or 'bennett-arith.bc' in a for a in source_link['argv'])
        nm = run([f'/usr/lib/llvm-{major}/bin/llvm-nm', '--undefined-only', out/'native-host.bc'])
        assert nm.returncode == 0 and b'printf' in nm.stdout, nm
        assert b'__rt_' not in nm.stdout and b'__bennett_dev_' not in nm.stdout, nm.stdout
        assert not list(out.glob('*/certificate.json')), 'native host has no device certificate'

        # A native library with no main is an object, never a fabricated process.
        libout = d/f'library-{major}'
        result = run([*args[:-1], f'--bennett-out={libout}', helper])
        assert result.returncode == 0, result.stderr.decode()
        library = json.loads((libout/'build.json').read_text())['outputs']['native_host']
        obj = pathlib.Path(library['path'])
        assert obj.suffix == '.o' and sha(obj) == library['sha256']
        symbols = run([f'/usr/lib/llvm-{major}/bin/llvm-nm', '--defined-only', obj])
        assert symbols.returncode == 0 and b'helper' in symbols.stdout, symbols

        # Mixed native machine input is deferred, with an explicit dependency.
        native = d/f'helper-{major}.o'
        cc = run([f'/usr/lib/llvm-{major}/bin/clang', '-c', helper, '-o', native])
        assert cc.returncode == 0, cc.stderr
        marked = d/f'marked-{major}.ll'
        marked.write_text(target_headers(major)+'''declare ptr @__bennett_qalloc(i64, i64)
declare void @__bennett_qfree(ptr)
define i32 @top() {
 %q = call ptr @__bennett_qalloc(i64 0, i64 1)
 call void @__bennett_qfree(ptr %q)
 ret i32 7
}
''')
        mixedout = d/f'mixed-{major}'
        refused = run([*args[:-1], f'--bennett-out={mixedout}', marked, native])
        error = refused.stderr.decode()
        assert refused.returncode != 0 and 'bennett-4ht' in error and 'bennett-driver-116' in error, error
        assert not (mixedout/'native-host').exists()
    assert original == {str(p): sha(p) for p in (main, helper)}
    print('Both majors: native-only stdio/argv/multi-TU process, library object, empty device inventory, explicit mixed-link dependency')
