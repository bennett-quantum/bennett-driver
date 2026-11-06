"""Concrete instance generation must precede real production normalisation."""
import hashlib,json,os,pathlib,subprocess,sys,tempfile
from contextlib import nullcontext
from toolchain import flags, configure, sibling
root=pathlib.Path(__file__).resolve().parents[1]
def run(args,limit=240):
 p=subprocess.run(list(map(str,args)),capture_output=True,timeout=limit)
 assert p.returncode==0,f'{args}: {p.returncode}\n{p.stderr.decode()}'
 return p.stdout
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
evidence=os.environ.get('BENNETT_DRIVER_ARITH_PRODUCTION_EVIDENCE')
if evidence:pathlib.Path(evidence).mkdir(parents=True,exist_ok=False)
with (nullcontext(evidence) if evidence else tempfile.TemporaryDirectory(dir=root/'.tmp',prefix='arith-production-')) as temp:
 d=pathlib.Path(temp)
 for major in (18,23):
  configure(major)
  llvm=pathlib.Path(f'/usr/lib/llvm-{major}/bin')
  seed=d/f'seed-{major}.c';seed.write_text('int main(void) { return 0; }')
  header='\n'.join(x for x in run([llvm/'clang','-S','-emit-llvm',seed,'-o','-']).decode().splitlines() if x.startswith('target '))+'\n'
  source=d/f'input-{major}.ll'
  source.write_text(header+'''declare ptr @__bennett_qalloc(i64, i64)
declare void @__bennett_qfree(ptr)
declare float @llvm.powi.f32.i7(float, i7)
define i32 @top() {
 %q = call ptr @__bennett_qalloc(i64 0, i64 1)
 call void @__bennett_qfree(ptr %q)
 %v = call float @llvm.powi.f32.i7(float 2.0, i7 3)
 %bits = bitcast float %v to i32
 ret i32 %bits
}
''')
  out=d/f'out-{major}'
  args=[sys.argv[1],*flags(major),f'--bennett-llvm-major={major}','-bennett-dialect=0.2.10',f'--bennett-out={out}',
    '--bennett-analysis-budget-ms=90000','-bennett-budget-default=10000000,1048576,65536,256,65536',source]
  run(args)
  request=json.loads((out/'arith-request.json').read_text())
  assert request['entries']==[dict(op='powi',base='f32',exponent_bits=7)],request
  record=json.loads((out/'manifest.json').read_text())
  stages=[x['stage'] for x in record['commands']]
  assert stages.index('arith-generate')<stages.index('arith-library-link')<stages.index('postlink')<stages.index('plugin')
  ir=run([llvm/'llvm-dis',out/'linked.bc','-o','-']).decode()
  assert 'define i32 @__bennett_sf_powi_f32_i7(' in ir and 'define i32 @__bennett_sf_powi_f32_i7_rm(' in ir
  assert record['arith_instances']['sha256']==sha(out/'arith-instances/bennett-arith.bc')
  assert any(x['entry']=='top' for x in json.loads((out/'launches.json').read_text()))
  assert record['status']=='complete'
  print(f'LLVM{major}: intrinsic request and generated literal definitions linked before real LTO/plugin; marked launch produced')
