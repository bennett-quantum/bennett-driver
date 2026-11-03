"""Comparison destinations cannot overwrite inputs or one another."""
import hashlib,json,pathlib,subprocess,sys,tempfile
from toolchain import flags, target_headers
root=pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(dir=root/'.tmp',prefix='output-paths-') as temp:
 d=pathlib.Path(temp)
 device=d/'device.ll';device.write_text('define i32 @main() { ret i32 0 }\n')
 layout=d/'layout.json';layout.write_text(json.dumps(dict(null_size=4096,ptr_width=64,heap_base=69632,
  heap_limit_max=1048576,globals={},interface_regions={})))
 inputs={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (device,layout)}
 symlink=d/'symlink.ll';symlink.symlink_to(device)
 hardlink=d/'hardlink.ll';hardlink.hardlink_to(device)
 cases=[('record-input',[f'--bennett-comparison-record={device}']),
  ('exe-input',[f'--bennett-comparison-output={device}']),
  ('record-symlink',[f'--bennett-comparison-record={symlink}']),
  ('exe-hardlink',[f'--bennett-comparison-output={hardlink}']),
  ('exe-layout',[f'--bennett-comparison-output={layout}']),
  ('record-exe',[f'--bennett-comparison-record={d/"same"}',f'--bennett-comparison-output={d/"same"}']),
  ('record-o0',[f'--bennett-comparison-record={d/"native-O0"}',f'--bennett-comparison-output={d/"native-O2"}']),
  ('same-o0',[f'--bennett-comparison-output={d/"native-O0"}']),
  ('record-manifest',['--bennett-comparison-record={out}/manifest.json']),
  ('exe-link-input',['--bennett-comparison-output={out}/comparison.bc'])]
 for major in (18,23):
  for name,extra in cases:
   out=d/f'{major}-{name}'
   extra=[arg.format(out=out) for arg in extra]
   p=subprocess.run([sys.argv[1],f'--bennett-llvm-major={major}',f'--bennett-materialised={device}',
    f'--bennett-out={out}',f'--bennett-comparison-layout={layout}','--bennett-layout-data-base=65536',*extra],
    capture_output=True,timeout=120)
   assert p.returncode and b'BD-E-OUTPUT-PATH' in p.stderr,(major,name,p.returncode,p.stderr)
   assert all(hashlib.sha256(path.read_bytes()).hexdigest()==sha for path,sha in inputs.items()),name
   assert not (out/'native-O2').exists() and not (out/'native-O0').exists(),name
  marked=d/f'marked-{major}.ll'
  marked.write_text(target_headers(major)+'''declare ptr @__bennett_qalloc(i64, i64)
declare void @__bennett_qfree(ptr)
define i32 @top() {
 %q = call ptr @__bennett_qalloc(i64 0, i64 1)
 call void @__bennett_qfree(ptr %q)
 ret i32 7
}
''')
  for name,option in [('host','record'),('linked','output')]:
   out=d/f'{major}-producer-{name}'
   target=out/f'{name}.bc'
   p=subprocess.run([sys.argv[1],*flags(major),f'--bennett-llvm-major={major}',
    '-bennett-dialect=0.2.10',f'--bennett-out={out}','--bennett-comparison=true',
    f'--bennett-comparison-{option}={target}',marked],capture_output=True,timeout=120)
   assert p.returncode and b'BD-E-OUTPUT-PATH' in p.stderr,(major,name,p.returncode,p.stderr)
   build=json.loads((out/'build.json').read_text())
   assert hashlib.sha256(target.read_bytes()).hexdigest()==build['outputs'][name]['sha256'],name
 print('Both majors: direct/symlink/hardlink input aliases and record/O2/O0 collisions refused before writes')
