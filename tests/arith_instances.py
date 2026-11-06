"""Exercise the producer's real offline generator, not a numerical stub."""
from toolchain import configure, sibling
import hashlib, json, pathlib, subprocess, sys, tempfile

root = pathlib.Path(__file__).resolve().parents[1]
def run(args):
    p = subprocess.run(list(map(str,args)), capture_output=True, timeout=240)
    assert p.returncode == 0, p.stderr.decode()
    return p.stdout
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

with tempfile.TemporaryDirectory(dir=root/'.tmp', prefix='arith-instances-') as temp:
    d = pathlib.Path(temp)
    for major in (18,23):
        configure(major)
        llvm = pathlib.Path(f'/usr/lib/llvm-{major}/bin')
        seed = d/f'seed-{major}.c';seed.write_text('int main(void) { return 0; }')
        header = run([llvm/'clang','-S','-emit-llvm',seed,'-o','-']).decode()
        header = '\n'.join(l for l in header.splitlines() if l.startswith('target '))+'\n'
        # Both spellings and a non-cache exponent width must be generated.
        ir = d/f'device-{major}.ll'
        ir.write_text(header+'''declare i32 @__bennett_sf_powi_f32_i7(i32, i7)
declare i32 @__bennett_sf_powi_f32_i193_rm(i32, i193, i32)
define i32 @main() {
 %a = call i32 @__bennett_sf_powi_f32_i7(i32 1073741824, i7 3)
 %b = call i32 @__bennett_sf_powi_f32_i193_rm(i32 1073741824, i193 3, i32 0)
 %x = icmp ne i32 %a, 1090519040
 %y = icmp ne i32 %b, 1090519040
 %bad = or i1 %x, %y
 %status = zext i1 %bad to i32
 ret i32 %status
}
''')
        digest = sha(ir)
        layout = d/f'layout-{major}.json'
        # Both O0/O2 link maps put data below 0x3f000. Retain exact equality
        # with that first page boundary, rather than reserving a guessed page.
        layout.write_text(json.dumps(dict(null_size=4096,ptr_width=64,heap_base=258048,
            heap_limit_max=1048576,globals={},interface_regions={})))
        out = d/f'out-{major}'
        run([sys.argv[1], f'--bennett-llvm-major={major}', f'--bennett-materialised={ir}',
            f'--bennett-out={out}', f'--bennett-comparison-layout={layout}',
            '--bennett-layout-data-base=249856'])
        assert sha(ir) == digest
        request = json.loads((out/'arith-request.json').read_text())
        assert request['entries'] == [dict(op='powi',base='f32',exponent_bits=k) for k in (7,193)], request
        manifest = json.loads((out/'arith-instances/manifest.json').read_text())
        assert manifest['request_sha256'] == sha(out/'arith-request.json')
        assert manifest['bitcode_sha256'] == sha(out/'arith-instances/bennett-arith.bc')
        symbols = {e['symbol']:e['function_type'] for e in manifest['exports']}
        assert symbols == {f'__bennett_sf_powi_f32_i{k}{suffix}': f'i32 (i32, i{k}'+(', i32)' if suffix else ')')
                           for k in (7,193) for suffix in ('','_rm')}, symbols
        for level in ('O0','O2'): assert run([out/f'native-{level}']) == b''
        receipt = json.loads((out/'manifest.json').read_text())
        assert receipt['arith_instances']['sha256'] == sha(out/'arith-instances/bennett-arith.bc')
        # Tamper with each trust binding. A producer manifest alone proves no type.
        original = (out/'arith-instances/manifest.json').read_text()
        for field in ('request_sha256','bitcode_sha256','function_type'):
            broken = json.loads(original)
            if field == 'function_type': broken['exports'][0][field] = 'i32 (i32, i32)'
            else: broken[field] = '0'*64
            (out/'arith-instances/manifest.json').write_text(json.dumps(broken,sort_keys=True,separators=(',',':')))
            p = subprocess.run(['python3',root/'scripts/arith-instances.py','verify',out, str(major)],capture_output=True)
            assert p.returncode and b'BD-E-ARITH-INSTANCES' in p.stderr, (field,p)
        (out/'arith-instances/manifest.json').write_text(original)

        # A matching manifest is insufficient: alter the actual export ABI,
        # update its bitcode digest honestly, and retain the requested type.
        instance=out/'arith-instances/bennett-arith.bc'
        original_bitcode=instance.read_bytes()
        bad_ir=d/f'wrong-literal-type-{major}.ll'
        lines=[header]
        for index,export in enumerate(manifest['exports']):
            result,args=export['function_type'].split(' (',1)
            args=args[:-1].split(', ')
            if index==0: args[1]='i'+str(int(args[1][1:])+1)
            params=', '.join(f'{ty} %p{i}' for i,ty in enumerate(args))
            lines.append(f'define {result} @{export["symbol"]}({params}) {{ ret {result} 0 }}')
        bad_ir.write_text('\n'.join(lines)+'\n')
        run([llvm/'llvm-as',bad_ir,'-o',instance])
        broken=json.loads(original);broken['bitcode_sha256']=sha(instance)
        (out/'arith-instances/manifest.json').write_text(json.dumps(broken,sort_keys=True,separators=(',',':')))
        p=subprocess.run(['python3',root/'scripts/arith-instances.py','verify',out,str(major)],capture_output=True)
        assert p.returncode and b'literal LLVM function type mismatch' in p.stderr,p.stderr
        instance.write_bytes(original_bitcode)
        (out/'arith-instances/manifest.json').write_text(original)
