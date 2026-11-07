"""Explicit new contract negotiation never changes an old caller's profile."""
import hashlib, json, os, pathlib, subprocess, sys, tempfile
from toolchain import target_headers, configure, sibling
root = pathlib.Path(__file__).resolve().parents[1]
plugin_root = sibling('bennett-plugin-native-comparison')
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
with tempfile.TemporaryDirectory(dir=root/'.tmp', prefix='dialect-profile-') as temp:
    d = pathlib.Path(temp)
    for major in (18, 23):
        configure(major)
        os.environ.pop('BENNETT_DRIVER_SYSROOT', None)  # This fixture retains ordinary host linking.
        plugin = plugin_root/f'build/libbennett-plugin-{major}.so'
        libraries = [f'--bennett-plugin={plugin}', f'--bennett-plugin-sha256={sha(plugin)}']
        for lib in ('runtimes', 'arith'):
            p = sibling(f'bennett-{lib}')/f'dist/llvm{major}/bennett-{lib}.bc'
            libraries += [f'--bennett-{lib}={p}', f'--bennett-{lib}-sha256={sha(p)}']
        source = d/f'marked-{major}.ll'
        source.write_text(target_headers(major)+'''declare ptr @__bennett_qalloc(i64, i64)
declare void @__bennett_qfree(ptr)
define i32 @top() {
 %q = call ptr @__bennett_qalloc(i64 0, i64 1)
 call void @__bennett_qfree(ptr %q)
 ret i32 7
}
!llvm.module.flags = !{!0}
!0 = !{i32 1, !"bennett.dialect", !"0.2.13"}
''')
        def build(label, version, path):
            out = d/f'{major}-{label}'
            p = subprocess.run([sys.argv[1], f'--bennett-llvm-major={major}',
                f'--bennett-dialect={version}', f'--bennett-out={out}', *libraries, str(path)],
                capture_output=True, timeout=120)
            return out, p
        out, result = build('modern', '0.2.13', source)
        assert result.returncode == 0, result.stderr
        record = json.loads((out/'build.json').read_text())
        assert (record['dialect'], record['isa'], record['plugin']['identity']) == ('0.2.13', '0.8', 'dialect-0.2.13;isa-0.8')
        for lib in ('plugin', 'runtimes', 'arith'):
            assert record[lib]['sha256'] == sha(pathlib.Path(record[lib]['path']))
        certificate = json.loads((out/'top/certificate.json').read_text())
        assert certificate['bindings']['dialect_mapping_version'] == '0.2.9'
        assert certificate['producer']['materialisation']['normaliser_version'] == '0.2.8'
        receipt = json.loads((out/'top/launch-record.json').read_text())
        assert receipt['artifacts']['top/certificate.json']['sha256'] == sha(out/'top/certificate.json')
        refused, result = build('explicit-old', '0.2.10', source)
        assert result.returncode and b'BD-E-VERSION' in result.stderr and b'expected dialect-0.2.10;isa-0.8' in result.stderr
        assert not (refused/'device.bc').exists()
        native = d/'native.c'
        native.write_text('int main(void) { return 13; }\n')
        out, result = build('native', '0.2.13', native)
        assert result.returncode == 0, result.stderr
        result = subprocess.run([out/'native-host'], capture_output=True, timeout=10)
        assert (result.returncode, result.stdout, result.stderr) == (13, b'', b'')
    print('Both majors: explicit dialect0.2.13/ISA0.8, actual artifact bindings/certificate mapping, mismatched old request rejected, native host preserved')
