"""Use the published plugin adapter on an actual produced marked module."""
import hashlib,json,os,pathlib,subprocess,sys,tempfile
from contextlib import nullcontext
from toolchain import target_headers
root=pathlib.Path(__file__).resolve().parents[1]
def run(args):
 p=subprocess.run(list(map(str,args)),capture_output=True,timeout=120)
 assert p.returncode==0,p.stderr.decode()
 return p.stdout
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
evidence=os.environ.get('BENNETT_DRIVER_NATIVE_EVIDENCE')
if evidence:pathlib.Path(evidence).mkdir(parents=True,exist_ok=False)
with (nullcontext(evidence) if evidence else tempfile.TemporaryDirectory(dir=root/'.tmp',prefix='native-materialisation-')) as temp:
 d=pathlib.Path(temp)
 for major in (18,23):
  source=d/f'marked-{major}.ll'
  source.write_text(target_headers(major)+'''declare ptr @__bennett_qalloc(i64, i64)
declare void @__bennett_qfree(ptr)
define i32 @top() {
 %q = call ptr @__bennett_qalloc(i64 0, i64 1)
 call void @__bennett_qfree(ptr %q)
 ret i32 7
}
''')
  production=d/f'production-{major}'
  run([sys.argv[1],f'--bennett-llvm-major={major}','-bennett-dialect=0.2.10',f'--bennett-out={production}',source])
  device=production/'device.bc';digest=sha(device)
  harness=d/f'harness-{major}.c';harness.write_text('extern int top(void); int main(void) { return top()!=7; }\n')
  layout=d/f'layout-{major}.json';layout.write_text(json.dumps(dict(null_size=4096,ptr_width=64,heap_base=69632,
   heap_limit_max=1048576,globals={},interface_regions={})))
  out=d/f'native-{major}'
  result=subprocess.run([sys.argv[1],f'--bennett-llvm-major={major}',f'--bennett-materialised={device}',
   '--bennett-comparison-entry=top',f'--bennett-native-input={harness}',f'--bennett-out={out}',
   f'--bennett-comparison-layout={layout}','--bennett-layout-data-base=65536'],capture_output=True,timeout=120)
  assert sha(device)==digest
  record=json.loads((out/'manifest.json').read_text())
  assert 'native_materialisation' in record,(result.returncode,result.stderr)
  stages=[c['stage'] for c in record['commands']]
  assert stages.index('native-prepare')<stages.index('comparison-checks')<stages.index('native-finalise')
  native=json.loads((out/'native-materialisation.json').read_text())
  assert native['binding_symbol']
  assert native['materialised_sha256']==digest
  assert native['record_sha256']==sha(production/'top/launch-record.json')
  ir=run([f'/usr/lib/llvm-{major}/bin/llvm-dis',out/'comparison.bc','-o','-']).decode()
  assert '@bennett_qreg_new(' in ir and '@bennett_qreg_free(' in ir
  undefined=run([f'/usr/lib/llvm-{major}/bin/llvm-nm','--undefined-only',out/'comparison.bc']).decode().splitlines()
  assert not {line.split()[-1] for line in undefined if line.split()}.intersection({'__bennett_qalloc','__bennett_qfree'})
  # This is adapter/provenance evidence. The strict freestanding link still
  # requires the real launch backend; a fake marker/backend is never supplied.
  assert result.returncode and b'BD-E-NATIVE-LINK' in result.stderr,result.stderr
  assert not (out/'native-O2').exists()
  for label,option in [('entry','--bennett-comparison-entry=missing'),
    ('plugin-pin','--bennett-plugin-sha256='+'0'*64)]:
   refused=d/f'{label}-{major}'
   args=[sys.argv[1],f'--bennett-llvm-major={major}',f'--bennett-materialised={device}',
    '--bennett-comparison-entry=top',f'--bennett-out={refused}']
   if label=='entry':
    args[3]=option
    args.append(f'--bennett-comparison-launch-record={production}/top/launch-record.json')
   else:args.append(option)
   p=subprocess.run(list(map(str,args)),capture_output=True,timeout=120)
   assert p.returncode and (b'BD-E-NATIVE-ADAPTER' in p.stderr if label=='entry' else b'BD-E-VERSION' in p.stderr),p.stderr
   assert sha(device)==digest and not (refused/'native-prepared.bc').exists()

 print('Both majors: actual materialisation prepare/check/finalise consumes entry provenance; real backend link remains explicit')
