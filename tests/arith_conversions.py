"""Real named-format instances: literal ABI, exact one, and fenv preservation."""
from toolchain import configure, sibling
import hashlib,json,os,pathlib,subprocess,sys,tempfile
from contextlib import nullcontext
root=pathlib.Path(__file__).resolve().parents[1]
def run(args):
    p=subprocess.run(list(map(str,args)),capture_output=True,timeout=300)
    assert p.returncode==0,f'{args}\n{p.stderr.decode()}'
    return p.stdout
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
# Exact one encodings from the published named formats (bias << fraction bits).
formats=dict(Float8E5M2=(8,60),Float8E5M2FNUZ=(8,64),Float8E4M3=(8,56),
 Float8E4M3FN=(8,56),Float8E4M3FNUZ=(8,64),Float8E4M3B11FNUZ=(8,88),
 Float8E3M4=(8,48),Float8E8M0FNU=(8,127),Float6E3M2FN=(6,12),
 Float6E2M3FN=(6,8),Float4E2M1FN=(4,2))
bases=dict(f16=(16,0x3c00),bf16=(16,0x3f80),f32=(32,0x3f800000),
 f64=(64,0x3ff0000000000000),f80=(80,0x3fff8000000000000000),
 f128=(128,0x3fff0000000000000000000000000000),ppcf128=(128,0x3ff0000000000000))
evidence=os.environ.get('BENNETT_DRIVER_ARITH_EVIDENCE')
if evidence:pathlib.Path(evidence).mkdir(parents=True,exist_ok=False)
with (nullcontext(evidence) if evidence else tempfile.TemporaryDirectory(dir=root/'.tmp',prefix='arith-conversions-')) as temp:
 d=pathlib.Path(temp);major=23;llvm=pathlib.Path('/usr/lib/llvm-23/bin')
 configure(major)
 seed=d/'seed.c';seed.write_text('int main(void) { return 0; }')
 header='\n'.join(x for x in run([llvm/'clang','-S','-emit-llvm',seed,'-o','-']).decode().splitlines() if x.startswith('target '))+'\n'
 declarations=['@__bennett_rt_fenv = external global { i32, i32 }, align 4']
 body=['define i32 @main() {',' %mode = getelementptr {i32,i32}, ptr @__bennett_rt_fenv, i32 0, i32 0',
       ' %flags = getelementptr {i32,i32}, ptr @__bennett_rt_fenv, i32 0, i32 1',
       ' store i32 4, ptr %mode',' store i32 31, ptr %flags']
 checks=[];exports={};entries=[]
 def check(value,ty,expected):
  name=f'check{len(checks)}';body.append(f' %{name} = icmp ne {ty} {value}, {expected}');checks.append(name)
 for base,(width,one) in bases.items():
  for fmt,(small,encoded) in formats.items():
   to=f'__bennett_sf_convert_to_{fmt}_{base}';fr=f'__bennett_sf_convert_from_{fmt}_{base}'
   declarations += [f'declare i{small} @{to}(i{width}, i32, i1)',f'declare i{width} @{fr}(i{small})']
   exports[to]=f'i{small} (i{width}, i32, i1)';exports[fr]=f'i{width} (i{small})'
   entries += [dict(op='convert_to',base=base,format=fmt),dict(op='convert_from',base=base,format=fmt)]
   for mode in range(5):
    for sat in ('false','true'):
     name=f'encoded{len(checks)}';body.append(f' %{name} = call i{small} @{to}(i{width} {one}, i32 {mode}, i1 {sat})')
     check('%'+name,f'i{small}',encoded)
   name=f'decoded{len(checks)}';body.append(f' %{name} = call i{width} @{fr}(i{small} {encoded})');check('%'+name,f'i{width}',one)
 body += [' %finalmode = load i32, ptr %mode',' %finalflags = load i32, ptr %flags']
 check('%finalmode','i32',4);check('%finalflags','i32',31)
 previous=checks[0]
 for i,name in enumerate(checks[1:]):
  current=f'bad{i}';body.append(f' %{current} = or i1 %{previous}, %{name}');previous=current
 body += [f' %status = zext i1 %{previous} to i32',' ret i32 %status','}']
 source=d/'device.ll';source.write_text(header+'\n'.join(declarations+body)+'\n');original=sha(source)
 # O0/O2 maps end at 0x3daa8/0x3dad8; keep the exact first-page equality.
 layout=d/'layout.json';layout.write_text(json.dumps(dict(null_size=4096,ptr_width=64,heap_base=253952,
  heap_limit_max=1048576,globals={},interface_regions={})))
 out=d/'native'
 run([sys.argv[1],f'--bennett-llvm-major={major}',f'--bennett-materialised={source}',f'--bennett-out={out}',
  f'--bennett-comparison-layout={layout}','--bennett-layout-data-base=249856'])
 assert sha(source)==original
 request=json.loads((out/'arith-request.json').read_text())
 assert request['entries']==sorted(entries,key=lambda e:(e['op'],e['base'],e['format']))
 manifest=json.loads((out/'arith-instances/manifest.json').read_text())
 assert manifest['request_sha256']==sha(out/'arith-request.json')
 assert manifest['bitcode_sha256']==sha(out/'arith-instances/bennett-arith.bc')
 assert {x['symbol']:x['function_type'] for x in manifest['exports']}==exports
 for level in ('O0','O2'):assert run([out/f'native-{level}'])==b''
 print('LLVM23: all 11 named formats x7 carriers, both directions, five modes and saturation; exact bits and fenv preserved')
