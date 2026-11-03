"""Every production IR input must declare its own target before linking."""
import pathlib,subprocess,sys,tempfile
from toolchain import target_headers
root=pathlib.Path(__file__).resolve().parents[1]
body='''declare ptr @__bennett_qalloc(i64, i64)
declare void @__bennett_qfree(ptr)
define i32 @top() {
 %q = call ptr @__bennett_qalloc(i64 0, i64 1)
 call void @__bennett_qfree(ptr %q)
 ret i32 7
}
'''
with tempfile.TemporaryDirectory(dir=root/'.tmp',prefix='input-headers-') as temp:
 d=pathlib.Path(temp)
 for major in (18,23):
  headers=target_headers(major)
  complete=d/f'complete-{major}.ll';complete.write_text(headers+body)
  cases=[('both',('triple','datalayout')),('triple',('triple',)),('layout',('datalayout',)),
   ('empty-triple',('triple',)),('empty-layout',('datalayout',))]
  for case,omitted in cases:
   partial='\n'.join(line for line in headers.splitlines() if not any(line.startswith('target '+field) for field in omitted))+'\n'
   if case.startswith('empty-'): partial+='target '+omitted[0]+' = "" ; explicitly empty is still missing\n'
   for position in ('first','second'):
    source=d/f'{major}-{case}-{position}.ll'
    source.write_text(partial+(body if position=='first' else 'define i32 @helper() { ret i32 0 }\n'))
    for spelling in ('ll','bc'):
     input_file=source if spelling=='ll' else source.with_suffix('.bc')
     if spelling=='bc':subprocess.run([f'/usr/lib/llvm-{major}/bin/llvm-as',source,'-o',input_file],capture_output=True,check=True)
     out=d/f'out-{major}-{case}-{position}-{spelling}'
     inputs=[input_file] if position=='first' else [complete,input_file]
     result=subprocess.run([sys.argv[1],f'--bennett-llvm-major={major}','-bennett-dialect=0.2.10',
       f'--bennett-out={out}',*inputs],capture_output=True,timeout=120)
     assert result.returncode and b'BD-E-VERSION' in result.stderr,(major,case,position,spelling,result.returncode,result.stderr)
     assert not (out/'linked.bc').exists(),(major,case,position,spelling)
 print('Both majors: first and later IR inputs with either/both target headers missing fail before linking')
