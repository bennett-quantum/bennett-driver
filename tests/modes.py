"""Published controls reach their backend, with real closed-unit processing."""
import json, pathlib, subprocess, sys, tempfile
from toolchain import flags, target_headers, configure, sibling
root = pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(dir=root/'.tmp', prefix='modes-') as temp:
    d = pathlib.Path(temp)
    for major in (18, 23):
        configure(major)
        source = d/f'marked-{major}.ll'
        source.write_text(target_headers(major)+'''declare ptr @__bennett_qalloc(i64, i64)
declare void @__bennett_qfree(ptr)
define i32 @top() {
 %q = call ptr @__bennett_qalloc(i64 0, i64 1)
 call void @__bennett_qfree(ptr %q)
 ret i32 7
}
''')
        def build(label, options):
            out = d/f'{major}-{label}'
            result = subprocess.run([sys.argv[1], *flags(major), f'--bennett-llvm-major={major}',
                '-bennett-dialect=0.2.10', f'--bennett-out={out}', *options, str(source)],
                capture_output=True, timeout=90)
            return out, result
        whole, result = build('whole', [])
        assert result.returncode == 0, result.stderr
        for spelling in ('-bennett-closed-unit', '--bennett-closed-unit=true'):
            out, result = build('closed-'+str(len(spelling)), [spelling])
            assert result.returncode == 0, result.stderr
            assert (out/'top/launch.bennett').read_bytes() == (whole/'top/launch.bennett').read_bytes()
            manifest = json.loads((out/'manifest.json').read_text())
            command = next(c for c in manifest['commands'] if c['stage'] == 'plugin')
            assert '-bennett-closed-unit=true' in command['argv']

        # The old immutable plugin does not register these published controls.
        # A backend dependency is explicit; parsing alone is never a pass.
        for label, options in [('oracle', ['--bennett-oracle=top', '--bennett-bind=0:in:8',
                '--bennett-bind=1:arg:8:3', '--bennett-dev=clock:64', '--bennett-dev=entropy:8', '--bennett-payload=return']),
            ('platform', ['--bennett-platform=riscv64-bennett-virt']),
            ('cpu', ['--bennett-cpu=generic'])]:
            out, result = build(label, options)
            assert result.returncode != 0 and b'BD-B-MODE-BACKEND' in result.stderr, (label,result.stderr)
            assert b'unimplemented driver option' not in result.stderr and b'empty or duplicate' not in result.stderr
            manifest = json.loads((out/'manifest.json').read_text())
            for option in options:
                assert option in manifest['options'], (label,manifest['options'])
            if label == 'oracle':
                assert not any(c['stage'] in ('postlink', 'plugin') for c in manifest['commands']), label
                assert b'before post-link optimisation' in result.stderr
            else:
                command = next(c for c in manifest['commands'] if c['stage'] == 'plugin')
                assert not command['success'] and 'Unknown command line argument' in command['stderr']
                for option in options:
                    assert option.lstrip('-') in [a.lstrip('-') for a in command['argv']], (label,command['argv'])
            assert not (out/'build.json').exists(), 'unavailable mode must not certify an unchanged build'
    print('Both majors: closed-unit output equals whole-program, all requested controls preserved, unavailable backend is blocked without a build certificate')
