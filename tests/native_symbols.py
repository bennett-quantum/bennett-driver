"""Resolved globals, interface buffers and arena objects keep exact ELF addresses."""
import hashlib,json,pathlib,subprocess,sys,tempfile
from toolchain import target_headers
root=pathlib.Path(__file__).resolve().parents[1]
def run(args):
 p=subprocess.run(list(map(str,args)),capture_output=True,timeout=120)
 assert p.returncode==0,p.stderr.decode()
 return p.stdout
with tempfile.TemporaryDirectory(dir=root/'.tmp',prefix='native-symbols-') as temp:
 d=pathlib.Path(temp)
 for major in (18,23):
  for kind in ('global','interface','arena'):
   symbol='counter' if kind=='global' else 'region'
   size=4 if kind=='global' else 16
   address=65536 if kind=='global' else 1118208
   declaration='@counter = global i32 7, align 4\n' if kind=='global' else '@region = global [16 x i8] zeroinitializer, align 8\n'
   read=' %v = load i32, ptr @counter\n %bad = icmp ne i32 %v, 7\n' if kind=='global' else ' store i8 19, ptr @region\n %v = load i8, ptr @region\n %bad = icmp ne i8 %v, 19\n'
   source=d/f'{major}-{kind}.ll'
   source.write_text(target_headers(major)+declaration+'define i32 @main() {\n'+read+f' %addr = ptrtoint ptr @{symbol} to i64\n %wrong = icmp ne i64 %addr, {address}\n %any = or i1 %bad, %wrong\n %r = zext i1 %any to i32\n ret i32 %r\n}}\n')
   digest=hashlib.sha256(source.read_bytes()).hexdigest()
   binding=dict(base=address,size=size,native_symbol=symbol,llvm_name=symbol,alignment=4 if kind=='global' else 8)
   layout=dict(null_size=4096,ptr_width=64,heap_base=69632,heap_limit_max=1048576,globals={},interface_regions={},materialised_sha256=digest)
   if kind=='global':layout['globals']={'G1':dict(binding,image='G1')}
   elif kind=='interface':layout['interface_regions']={'entry':{'input':binding}}
   else:layout['arena']=binding
   path=d/f'{major}-{kind}.json';path.write_text(json.dumps(layout))
   out=d/f'{major}-{kind}-out'
   run([sys.argv[1],f'--bennett-llvm-major={major}',f'--bennett-materialised={source}',
     f'--bennett-out={out}',f'--bennett-comparison-layout={path}','--bennett-layout-data-base=65536'])
   assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
   for level in ('O0','O2'):assert run([out/f'native-{level}'])==b''
   resolved=json.loads((out/'resolved-layout.json').read_text())
   assert resolved['native_bindings'][0]['native_symbol']==symbol
   for name,change in [('hash',{'materialised_sha256':'0'*64}),
     ('missing',{'globals':{'G1':dict(base=65536,size=4,image='G1')}})]:
    if kind!='global':continue
    invalid=d/f'{major}-{name}.json';invalid.write_text(json.dumps(layout|change))
    p=subprocess.run([sys.argv[1],f'--bennett-llvm-major={major}',f'--bennett-materialised={source}',
     f'--bennett-out={d/f"{major}-{name}"}',f'--bennett-comparison-layout={invalid}','--bennett-layout-data-base=65536'],capture_output=True,timeout=120)
    assert p.returncode and b'BD-E-NATIVE-LAYOUT' in p.stderr,p.stderr
 print('Both majors: mapped globals/interface/arena preserve actual addresses and values at O0/O2; stale/missing maps fail')
