"""The published function-pointer case must fall back without rejection."""
import hashlib, os, pathlib, subprocess, sys, tempfile
from toolchain import flags, target_headers, configure, sibling
root = pathlib.Path(__file__).resolve().parents[1]
plugin_root = sibling('bennett-plugin-native-comparison')
with tempfile.TemporaryDirectory(dir=root/'.tmp', prefix='closed-unit-') as temp:
    d = pathlib.Path(temp)
    for major in (18, 23):
        configure(major)
        source = d/f'callback-{major}.ll'
        plugin = plugin_root/f'build/libbennett-plugin-{major}.so'
        plugin_flags = [f'--bennett-plugin={plugin}', '--bennett-plugin-sha256='+hashlib.sha256(plugin.read_bytes()).hexdigest()]
        def build(label, options):
            out = d/f'{major}-{label}'
            result = subprocess.run([sys.argv[1], *flags(major, plugin=False), *plugin_flags, f'--bennett-llvm-major={major}',
                '-bennett-dialect=0.2.13', f'--bennett-out={out}', *options, str(source)],
                capture_output=True, timeout=90)
            return out, result
        source.write_text(target_headers(major)+'''declare ptr @__bennett_qalloc(i64, i64)
declare void @__bennett_qfree(ptr)
@address = global ptr @g
define internal i8 @g() { ret i8 7 }
define i8 @entry(ptr %p) {
 %q = call ptr @__bennett_qalloc(i64 0, i64 1)
 %r = call i8 %p()
 call void @__bennett_qfree(ptr %q)
 ret i8 %r
}
''')
        ordinary, result = build('fallback-whole', [])
        assert result.returncode == 0, result.stderr
        fallback, result = build('fallback-closed', ['-bennett-closed-unit'])
        assert result.returncode == 0, result.stderr
        assert (ordinary/'entry/launch.bennett').read_bytes() == (fallback/'entry/launch.bennett').read_bytes()
    print('Both majors: function-pointer entry accepts whole and closed-unit requests with identical ISA output')
