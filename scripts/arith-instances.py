"""Collect/verify the published §13.1 static instantiation wire contract.

No producer implementation is imported. Verification reads ordinary LLVM IR
using the selected major's public tools and compares literal function types.
"""
import hashlib, json, pathlib, re, subprocess, sys

mode, output, major, *inputs = sys.argv[1:]
out, major = pathlib.Path(output), int(major)
bases = dict(f16=16, bf16=16, f32=32, f64=64, f80=80, f128=128, ppcf128=128)
formats = {name:8 for name in ('Float8E5M2','Float8E5M2FNUZ','Float8E4M3','Float8E4M3FN',
    'Float8E4M3FNUZ','Float8E4M3B11FNUZ','Float8E3M4','Float8E8M0FNU')}
formats.update(Float6E3M2FN=6, Float6E2M3FN=6, Float4E2M1FN=4)
def fail(message): raise ValueError('BD-E-ARITH-INSTANCES: §13.1 '+message)
def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def key(e): return e['op'],e['base'],e.get('format',''),e.get('exponent_bits',0)
def expected(entries):
    result = {}
    for entry in entries:
        op, base = entry['op'], entry['base']
        if base not in bases: fail('invalid carrier suffix '+base)
        carrier = 'i'+str(bases[base])
        if op == 'powi':
            k = entry['exponent_bits']
            if type(k) is not int or not 1 <= k <= 8388608: fail('invalid exact exponent width')
            for suffix in ('','_rm'):
                result[f'__bennett_sf_powi_{base}_i{k}{suffix}'] = f'{carrier} ({carrier}, i{k}'+(', i32)' if suffix else ')')
        else:
            fmt = entry['format']
            if major != 23 or fmt not in formats: fail('format is absent from selected LLVM major: '+fmt)
            small = 'i'+str(formats[fmt])
            name = f'__bennett_sf_{op}_{fmt}_{base}'
            result[name] = f'{small} ({carrier}, i32, i1)' if op == 'convert_to' else f'{carrier} ({small})'
    return [dict(symbol=s,function_type=result[s]) for s in sorted(result)]
def pairs(items):
    result = {}
    for k,v in items:
        if k in result: fail('duplicate JSON key '+k)
        result[k] = v
    return result
def load(p): return json.loads(p.read_bytes(),object_pairs_hook=pairs)

try:
    request_path = out/'arith-request.json'
    if mode == 'collect':
        entries = {}
        headers = {}
        def add(e): entries[key(e)] = e
        for filename in inputs:
            text = pathlib.Path(filename).read_text()
            for field, spelling in (('target_triple','triple'),('data_layout','datalayout')):
                match = re.search(r'^target '+spelling+r' = "([^"\n]+)"$',text,re.M)
                if match:
                    if field in headers and headers[field] != match[1]: fail('mixed '+field)
                    headers[field] = match[1]
            # Collect direct concrete references as well as pre-normalisation
            # LLVM intrinsics, including constrained and scalarised vector forms.
            for base,k in re.findall(r'@__bennett_sf_powi_(\w+?)_i(\d+)(?:_rm)?\b',text):
                add(dict(op='powi',base=base,exponent_bits=int(k)))
            for base,k in re.findall(r'@llvm\.(?:experimental\.constrained\.)?powi\.(?:nxv\d+|v\d+)?(f16|bf16|f32|f64|f80|f128|ppcf128)\.i(\d+)\b',text):
                add(dict(op='powi',base=base,exponent_bits=int(k)))
            for op,fmt,base in re.findall(r'@__bennett_sf_(convert_to|convert_from)_(\w+)_(f16|bf16|f32|f64|f80|f128|ppcf128)\b',text):
                add(dict(op=op,format=fmt,base=base))
            for line in text.splitlines():
                match = re.search(r'\b(?:call|invoke)\b.*@llvm\.convert\.(to|from)\.arbitrary\.fp\.([^ (]+)\((.*)\)',line)
                if not match: continue
                direction, suffix, args = match.groups()
                candidates = [re.sub(r'^(?:nxv\d+|v\d+)','',part) for part in suffix.split('.')]
                base = next((b for b in candidates if b in bases),None)
                fmt = re.search(r'metadata !"([^"]+)"',args)
                if not base or not fmt: fail('conversion lacks literal interpretation MDString/carrier: '+line)
                add(dict(op='convert_'+direction,format=fmt[1],base=base))
        if not entries:
            print('none')
        else:
            entries = sorted(entries.values(),key=key)
            expected(entries)  # Validate the published domain, never a cache width cap.
            if set(headers) != {'target_triple','data_layout'}: fail('instances require explicit target triple/data layout in verified IR')
            request = dict(schema='bennett-arith-instantiations-1',llvm_major=major,**headers,entries=entries)
            request_path.write_bytes(canonical(request))
            print('required')
    elif mode == 'verify':
        request = load(request_path)
        publication = out/'arith-instances'
        manifest_path = publication/'manifest.json'
        manifest = load(manifest_path)
        bitcode = publication/'bennett-arith.bc'
        if request_path.read_bytes() != canonical(request): fail('noncanonical request')
        if manifest_path.read_bytes() != canonical(manifest): fail('noncanonical producer manifest')
        if manifest['schema'] != 'bennett-arith-instances-1': fail('producer schema mismatch')
        for field in ('llvm_major','target_triple','data_layout'):
            if manifest[field] != request[field]: fail('producer '+field+' mismatch')
        if request['llvm_major'] != major: fail('request major mismatch')
        if manifest['request_sha256'] != digest(request_path): fail('request SHA256 mismatch')
        if manifest['bitcode_sha256'] != digest(bitcode): fail('bitcode SHA256 mismatch')
        exports = expected(request['entries'])
        if manifest['exports'] != exports: fail('producer export types/set/order mismatch')
        commands = []
        def tool(name,*args):
            argv = [f'/usr/lib/llvm-{major}/bin/{name}',*map(str,args)]
            commands.append(argv)
            p = subprocess.run(argv,capture_output=True,timeout=60)
            if p.returncode: fail(name+': '+p.stderr.decode())
            return p.stdout.decode()
        ir = tool('llvm-dis',bitcode,'-o','-')
        for field, spelling in (('target_triple','triple'),('data_layout','datalayout')):
            if f'target {spelling} = "{request[field]}"' not in ir: fail('bitcode '+field+' mismatch')
        for export in exports:
            match = re.search(r'^define ([^\n@]+)@'+re.escape(export['symbol'])+r'\(([^\n)]*)\)',ir,re.M)
            if not match: fail('missing definition '+export['symbol'])
            result_type = re.search(r'\b(i\d+)\s*$',match[1])
            arg_types = []
            for arg in match[2].split(','):
                arg_type = re.match(r'\s*(i\d+)\b',arg)
                if not arg_type: fail('noninteger/vararg export '+export['symbol'])
                arg_types.append(arg_type[1])
            actual = (result_type[1] if result_type else '?')+' ('+', '.join(arg_types)+')'
            if actual != export['function_type']: fail('literal LLVM function type mismatch '+export['symbol']+': '+actual)
        if re.search(r'\b(?:fadd|fsub|fmul|fdiv|frem|fcmp|fptosi|fptoui|sitofp|uitofp|fpext|fptrunc)\b',ir): fail('hardware FP in generated closure')
        imports = [line.split()[-1] for line in tool('llvm-nm','--undefined-only',bitcode).splitlines() if line.split()]
        # §13.5 state belongs to runtimes and is resolved in the final link.
        runtime_imports = {'__bennett_rt_fenv'}
        if any(not s.startswith('llvm.') and s not in runtime_imports for s in imports): fail('unresolved/host import: '+', '.join(imports))
        (out/'arith-verification.json').write_bytes(canonical(dict(schema='bennett-driver-arith-verification-1',exports=exports,commands=commands,runtime_imports=sorted(set(imports)&runtime_imports),request_sha256=digest(request_path),bitcode_sha256=digest(bitcode))))
    else:
        fail('unknown operation '+mode)
except (ValueError,KeyError,OSError,TypeError,subprocess.TimeoutExpired) as e:
    print(str(e) if str(e).startswith('BD-E-') else 'BD-E-ARITH-INSTANCES: '+str(e),file=sys.stderr)
    sys.exit(1)
