"""Certificate pipeline provenance must agree with the command actually run."""
import hashlib,json,pathlib,subprocess,sys,tempfile
from toolchain import flags, target_headers, configure, sibling
root=pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(dir=root/'.tmp',prefix='pipeline-metadata-') as temp:
 d=pathlib.Path(temp)
 for major in (18,23):
  configure(major)
  source=d/f'input-{major}.ll'
  source.write_text(target_headers(major)+'''declare ptr @__bennett_qalloc(i64, i64)
declare void @__bennett_qfree(ptr)
define i32 @top() {
 %q = call ptr @__bennett_qalloc(i64 0, i64 1)
 call void @__bennett_qfree(ptr %q)
 ret i32 7
}
''')
  for name,option,pipeline in [('single','-bennett-pipeline=default<O0>','default<O0>'),
   ('double','--bennett-pipeline=default<O0>','default<O0>'),('default',None,'lto<O3>')]:
   out=d/f'{major}-{name}'
   args=[sys.argv[1],*flags(major),f'--bennett-llvm-major={major}','-bennett-dialect=0.2.10',f'--bennett-out={out}',source]
   if option:args.insert(1,option)
   result=subprocess.run(list(map(str,args)),capture_output=True,timeout=120)
   assert result.returncode==0,result.stderr
   manifest=json.loads((out/'manifest.json').read_text())
   postlink=next(x for x in manifest['commands'] if x['stage']=='postlink')
   assert f'-passes={pipeline}' in postlink['argv']
   certificate=json.loads((out/'top/certificate.json').read_text())
   assert certificate['producer']['materialisation']['pipeline']==pipeline+',bennett',(major,name,certificate['producer'])
   build=json.loads((out/'build.json').read_text())
   assert build['pipeline']==pipeline
   receipt=json.loads((out/'top/launch-record.json').read_text())
   assert receipt['artifacts']['top/certificate.json']['sha256']==hashlib.sha256((out/'top/certificate.json').read_bytes()).hexdigest()
  failed=d/f'failed-comparison-{major}'
  malformed=d/f'malformed-layout-{major}.json'
  malformed.write_text('{}')
  result=subprocess.run([sys.argv[1],*flags(major),f'--bennett-llvm-major={major}',
      '-bennett-dialect=0.2.10',f'--bennett-out={failed}', '--bennett-comparison=true',
      f'--bennett-comparison-layout={malformed}',source],capture_output=True,timeout=120)
  assert result.returncode != 0, result.stderr
  manifest=json.loads((failed/'manifest.json').read_text())
  assert manifest['status'] == 'failed', manifest
  build=json.loads((failed/'build.json').read_text())
  assert build['status'] == manifest['status'], (build['status'], manifest['status'])
  assert build['error'] == manifest['error']
 print('Both majors: single/double-dash and default pipelines agree across executed command/build/certificate/receipt')
