"""Independent source/native and merged-bitcode oracles for multi-module linking."""
from toolchain import flags, configure
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def run(args):
    result = subprocess.run(list(map(str, args)), capture_output=True, timeout=45)
    assert result.returncode == 0, (args, result.stderr)
    return result


with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'], prefix='merged-module-') as temp:
    directory = Path(temp)
    for major in (18, 23):
        configure(major)
        llvm = Path(f'/usr/lib/llvm-{major}/bin')
        main = directory/'main.c'
        helper = directory/'helper.c'
        marker = directory/'selected.c'
        main.write_text('extern int helper(int); int main(int argc, char **argv) { return helper(argc - 1); }\n')
        helper.write_text('volatile int offset = 13; int helper(int n) { return 7*n + offset; }\n')
        marker.write_text('extern void *__bennett_qalloc(unsigned long, unsigned long); extern void __bennett_qfree(void *); int top(void) { void *q=__bennett_qalloc(0,1); __bennett_qfree(q); return 0; }\n')
        oracle = directory/f'oracle-{major}'
        run([llvm/'clang', main, helper, '-o', oracle])
        out = directory/f'build-{major}'
        run([sys.argv[1], *flags(major), f'--bennett-llvm-major={major}',
             '--bennett-dialect=0.2.10', f'--bennett-out={out}', main, helper, marker])
        # Lazy entry compilation executes the real postlink.bc without trying
        # to resolve device markers in the separate, uncalled selected entry.
        for count in range(9):
            arguments = ['argument'] * count
            expected = 7*count + 13
            native = subprocess.run([oracle, *arguments], capture_output=True, timeout=10)
            merged = subprocess.run([llvm/'lli', '--jit-kind=orc-lazy', out/'postlink.bc', *arguments], capture_output=True, timeout=10)
            assert (native.returncode, native.stdout, native.stderr) == (expected, b'', b''), native
            assert (merged.returncode, merged.stdout, merged.stderr) == (expected, b'', b''), merged
        # A changed helper is observable: an omitted/wrong module cannot satisfy
        # merely an equality between two driver outputs.
        helper.write_text(helper.read_text().replace('7*n', '8*n'))
        run([llvm/'clang', main, helper, '-o', oracle])
        wrong = subprocess.run([oracle, 'argument'], capture_output=True, timeout=10)
        assert wrong.returncode == 21 and wrong.returncode != 20, wrong
