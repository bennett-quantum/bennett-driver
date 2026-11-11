"""Driver-owned process inputs survive real R preparation, exit and reversal."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from contextlib import nullcontext
from toolchain import configure, sibling
from process_arguments_codec import check_codec

SOURCE = '''#include <stdio.h>
#include <stdlib.h>
extern char **environ;
typedef void (*finalizer)(void);
/* This fixture has no static finalizers; its registered atexit handler is real. */
finalizer const __fini_array_start[0] = {};
extern finalizer const __fini_array_end[0] __attribute__((alias("__fini_array_start")));
static void finish(void) { puts("bye"); }
int main(int argc, char **argv, char **envp) {
 if (argc != 3 || !argv || !envp || environ != envp || argv[argc] || envp[2]) return 81;
 if (argv[1][0] != 'a' || argv[1][1] != 'b' || argv[1][2] != 'c' || argv[1][3] || argv[2][0]) return 82;
 char *value = getenv("VALUE");
 if (!value || value[0] != 'a' || value[1] != 'b' || value[2] != 'c' || value[3]) return 83;
 if (atexit(finish)) return 84;
 puts(argv[1]);
 return 7;
}
'''


def run(argv):
    result = subprocess.run(list(map(str, argv)), capture_output=True, timeout=180)
    assert result.returncode == 0, result.stderr.decode()
    return result.stdout


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_replies(replies):
    # Hand-derived header, offsets and bytes; no implementation serializer oracle.
    strings = b'program\0abc\0\0VALUE=abc\0EMPTY=\0'
    expected = struct.pack('<IIQQ', 3, 0, 2, 24 + 7 * 8 + len(strings))
    expected += struct.pack('<7Q', 80, 88, 92, 0, 93, 103, 0) + strings
    assert replies == [dict(service='bennett.argv.bytes', payload='00' * 24, reply=expected.hex()),
                       dict(service='bennett.argv.bytes', payload='00' * len(expected), reply=expected.hex())]


def run_major(binary, directory, major):
    paths = configure(major)
    plugin = sibling('bennett-plugin-r-contract') / f'build/libbennett-plugin-{major}.so'
    source = directory / f'process-{major}.c'
    source.write_text(SOURCE)
    context = directory / f'context-{major}.json'
    context.write_text(json.dumps(dict(schema='bennett-driver-process-arguments-1',
                                      argv=['program', 'abc', ''], envp=['VALUE=abc', 'EMPTY='])))
    out = directory / f'out-{major}'
    run([binary, f'--bennett-llvm-major={major}', '-bennett-dialect=0.3-r1', '-bennett-isa=0.9',
         '--bennett-tier=reversible', '--bennett-entry=main', f'--bennett-plugin={plugin}',
         *[f'--bennett-{key}={paths[key]}' for key in ('runtimes', 'arith', 'sysroot')],
         f'--bennett-process-arguments={context}', f'--bennett-out={out}',
         '--bennett-analysis-budget-ms=300000',
         '-bennett-budget-default=10000000,1048576,65536,256,65536', source])
    build = json.loads((out / 'main/build.json').read_text())
    assert build['entry_initialisation']['arguments'] == 'bennett-argv-bytes-1'
    manifest = json.loads((out / 'manifest.json').read_text())
    assert manifest['status'] == 'complete', manifest['status']
    assert manifest['process_arguments']['sha256'] == sha(context)
    assert manifest['process_preparation']['helper_type'] == 'void (i32, ptr, ptr)'
    receipt = json.loads((out / 'main/launch-record.json').read_text())
    replies = out / 'main/argv-replies.json'
    check_replies(json.loads(replies.read_text()))
    assert receipt['artifacts']['main/argv-replies.json']['sha256'] == sha(replies)
    publication = {p: sha(p) for p in out.rglob('*') if p.is_file()}
    run([directory / 'reference-process', out / 'main/launch.bennett', replies])
    assert {p: sha(p) for p in out.rglob('*') if p.is_file()} == publication
    print(f'LLVM{major}: complete driver R process, real argv/envp/getenv, exit7, abc+bye output, whole-run restoration')


def check_option_policy(binary, directory):
    context = directory / 'option-context.json'
    context.write_text(json.dumps(dict(schema='bennett-driver-process-arguments-1', argv=[], envp=[])))
    source = directory / 'option-source.c'
    source.write_text('int main(void) { return 0; }\n')
    for name, options, message in [
        ('tier', [], b'require --bennett-tier=reversible'),
        ('duplicate', ['--bennett-tier=reversible', '--bennett-entry=main',
                       f'--bennett-argv-replies={context}'], b'choose process arguments or explicit argv replies')]:
        result = subprocess.run([binary, '-bennett-dialect=0.3-r1', f'--bennett-out={directory / name}',
            f'--bennett-process-arguments={context}', *options, str(source)], capture_output=True)
        assert result.returncode != 0 and message in result.stderr, result.stderr


def compile_reference(directory):
    release = sibling('bennett-isa-spec-review') / 'reference-interpreter/target/release'
    source = Path(__file__).resolve().parent / 'fixtures/r_process_reference.rs'
    run(['rustc', '--edition=2021', '-O', source,
         '-L', f'dependency={release / "deps"}', '--extern',
         f'bennett_isa_ref={release / "libbennett_isa_ref.rlib"}',
         '-o', directory / 'reference-process'])


evidence = os.environ.get('BENNETT_DRIVER_PROCESS_ARGUMENT_EVIDENCE')
if evidence:
    Path(evidence).mkdir(parents=True, exist_ok=False)
with (nullcontext(evidence) if evidence else tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'], prefix='r-process-arguments-')) as temp:
    check_option_policy(sys.argv[1], Path(temp))
    check_codec(Path(temp))
    compile_reference(Path(temp))
    failures = []
    for major in (18, 23):
        try:
            run_major(sys.argv[1], Path(temp), major)
        except (AssertionError, KeyError) as error:
            failures.append(f'LLVM{major}: {error}')
    assert not failures, '\n'.join(failures)
