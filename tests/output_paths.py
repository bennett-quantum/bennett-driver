"""Comparison destinations cannot overwrite inputs or one another."""
import hashlib,json,pathlib,subprocess,sys,tempfile
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
 print('Both majors: direct/symlink/hardlink input aliases and record/O2/O0 collisions refused before writes')
