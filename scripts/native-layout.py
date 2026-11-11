"""Resolve comparison placements and audit their actual native ELF symbols.

Explicit comparison-layout files may annotate device ranges with native_symbol,
llvm_name/native_section, size and alignment. These are driver adapter fields,
not additions to the ISA object's layout grammar.
"""
import hashlib,json,pathlib,subprocess,sys

def fail(message):
    raise ValueError('BD-E-NATIVE-LAYOUT: §19.5 '+message)
def integer(value,name):
    if type(value) is not int or not 0<=value<2**63:fail('invalid '+name)
    return value
def quoted(value):
    if not isinstance(value,str) or not value or '\0' in value:fail('invalid native symbol/section')
    return json.dumps(value,ensure_ascii=False)
def audit(major,binary,layout):
    bindings=json.loads(pathlib.Path(layout).read_text()).get('native_bindings',[])
    if not bindings:return
    argv=[f'/usr/lib/llvm-{major}/bin/llvm-nm','--defined-only','--print-size','--format=posix',binary]
    result=subprocess.run(argv,capture_output=True,text=True,timeout=60)
    if result.returncode:fail('cannot audit ELF symbols: '+result.stderr)
    symbols={}
    for line in result.stdout.splitlines():
        if not line.strip():continue
        fields=line.rsplit(maxsplit=3)
        if len(fields)!=4:fail('malformed ELF symbol row: '+line)
        name,kind,address,size=fields
        symbols[name]=(kind,int(address,16),int(size,16))
    for binding in bindings:
        name=binding['native_symbol']
        if name not in symbols:fail('native ELF lacks mapped symbol '+name)
        kind,address,size=symbols[name]
        if kind.upper() not in ('B','D','R','G','S','C','V') and kind!='u':fail('mapped symbol is not a data object: '+name)
        if address!=binding['base'] or size!=binding['size'] or address%binding['alignment']:
            fail('ELF address/size/alignment differs from resolved range '+binding['key'])
    print(f'validated {len(bindings)} native ELF range bindings')

def digest(path):
    data=pathlib.Path(path).read_bytes()
    return hashlib.sha256(data).hexdigest()

def publication(device,report,receipt_path,entry):
    receipt_path=pathlib.Path(receipt_path)
    receipt=json.loads(receipt_path.read_text())
    if report['schema']!='bennett-native-comparison-1' or report['phase']!='prepared':fail('invalid preparation report')
    if receipt['entry']!=entry or report['entries']!=[entry]:fail('native mapping selected entry mismatch')
    if report['record_sha256']!=digest(receipt_path):fail('native mapping launch record SHA256 mismatch')
    if report['materialised_sha256']!=digest(device):fail('native mapping materialised SHA256 mismatch')
    artifacts=receipt['artifacts']
    for name,path in [('device.bc',device),(entry+'/launch.bennett',receipt_path.parent/'launch.bennett'),
                      (entry+'/build.json',receipt_path.parent/'build.json')]:
        if artifacts[name]['sha256']!=digest(path):fail('native mapping artifact SHA256 mismatch: '+name)
    launch=receipt_path.parent/'launch.bennett'
    if report['launch_sha256']!=digest(launch):fail('native mapping launch SHA256 mismatch')
    layout=json.loads(launch.read_text().split('\nsection layout\n',1)[1].splitlines()[0])
    build=json.loads((receipt_path.parent/'build.json').read_text())
    if build['layout']!=layout:fail('native mapping build/launch layout mismatch')
    mapping=build['native_global_mapping']
    if mapping['schema']!='bennett-device-native-globals-1':fail('invalid device-native mapping schema')
    return layout,mapping['globals']

def global_annotations(mapping,symbols):
    rows=[s for s in symbols if s['kind']=='global' and s['source_key']==mapping['source_key']]
    if len(rows)!=1:fail('native mapping lacks one unique source symbol: '+mapping['source_key'])
    row=rows[0]
    if row['native_symbol']!=mapping['native_symbol'] or row['size']!=mapping['size']:
        fail('native mapping symbol/size mismatch: '+mapping['source_key'])
    return {key:row[key] for key in ('native_symbol','llvm_name','alignment')}

def apply_handoff(layout,device,report_path,receipt_path,entry):
    if not report_path:return
    report=json.loads(pathlib.Path(report_path).read_text())
    # Historical reports carry no device correspondence; they retain explicit maps.
    if 'device_globals' not in report:return
    published,mapping=publication(device,report,receipt_path,entry)
    globals_=report['device_globals']
    if set(globals_)!=set(published['globals']) or set(globals_)!=set(layout['globals']) or set(globals_)!=set(mapping):
        fail('native mapping device-global inventory mismatch')
    sources=[]
    for name,value in globals_.items():
        key='global '+name
        expected={k:value[k] for k in ('source_key','base','size')}
        if expected!=mapping[name]:fail('native mapping differs from authenticated association: '+key)
        for field in ('base','size','image'):
            if layout['globals'][name][field]!=published['globals'][name][field]:fail('native mapping layout mismatch: '+key)
        if value['base']!=published['globals'][name]['base'] or value['size']!=published['globals'][name]['size']:
            fail('native mapping range mismatch: '+key)
        sources.append(value['source_key'])
        for field,annotation in global_annotations(value,report['symbols']).items():
            if field in layout['globals'][name] and layout['globals'][name][field]!=annotation:fail('conflicting native mapping '+field+': '+key)
            layout['globals'][name][field]=annotation
    if len(set(sources))!=len(sources):fail('duplicate native mapping source identity')
    materialised=digest(device)
    if 'materialised_sha256' in layout and layout['materialised_sha256']!=materialised:fail('native mapping materialised SHA256 mismatch')
    layout['materialised_sha256']=materialised

def read_layout(device,explicit):
    if explicit:layout=json.loads(pathlib.Path(explicit).read_text())
    else:
        launches=device.parent/'launches.json'
        if not launches.is_file():fail('missing resolved layout: supply --bennett-comparison-layout=FILE or adjacent launches.json')
        layouts=[]
        for entry in json.loads(launches.read_text()):
            text=(device.parent/entry['object']).read_text()
            if '\nsection layout\n' not in text:fail('launch has no resolved layout: '+entry['object'])
            layouts.append(json.loads(text.split('\nsection layout\n',1)[1].splitlines()[0]))
        if not layouts or any(x!=layouts[0] for x in layouts):fail('device entries lack one common resolved layout; select an explicit entry layout')
        layout=layouts[0]
    return layout

def prepare(out,device,explicit,data_arg,text_arg,report='',receipt='',entry=''):
    out,device=pathlib.Path(out),pathlib.Path(device)
    layout=read_layout(device,explicit)
    if type(layout) is not dict or type(layout['globals']) is not dict or type(layout['interface_regions']) is not dict:fail('malformed global/interface layout')
    apply_handoff(layout,device,report,receipt,entry)
    base=integer(layout['heap_base'],'heap_base');limit=integer(layout['heap_limit_max'],'heap_limit_max')
    if layout['null_size']!=4096 or layout['ptr_width']!=64:fail('native closure requires LP64 and 4096-byte null region')
    if base<4096 or base%4096 or base+limit>=2**63:fail('unaligned/overflowing heap range')
    bindings=[]
    def bind(key,value):
        if type(value) is not dict or not value.get('native_symbol'):fail('missing native symbol mapping for '+key)
        start=integer(value['base'],key+' base');size=integer(value['size'],key+' size')
        alignment=integer(value.get('alignment',1),key+' alignment')
        if not alignment or alignment&(alignment-1) or start%alignment:fail('invalid range alignment for '+key)
        end=start+max(1,size)
        if start<4096 or end>=2**63 or (start<base+limit and end>base):fail('mapped range overlaps null/heap or overflows: '+key)
        symbol=value['native_symbol'];quoted(symbol)
        llvm=value.get('llvm_name',symbol)
        sections=[value['native_section']] if 'native_section' in value else [prefix+llvm for prefix in ('.data.','.bss.','.rodata.')]
        for section in sections:quoted(section)
        bindings.append(dict(key=key,base=start,size=size,alignment=alignment,native_symbol=symbol,sections=sections))
    for name,value in layout['globals'].items():bind('global '+name,value)
    for owner,regions in layout['interface_regions'].items():
        for name,value in regions.items():bind('interface '+owner+'/'+name,value)
    if layout.get('arena'):bind('arena',layout['arena'])
    if bindings:
        if layout.get('materialised_sha256')!=hashlib.sha256(device.read_bytes()).hexdigest():fail('native mapping materialised SHA256 mismatch')
        bindings.sort(key=lambda value:value['base'])
        for left,right in zip(bindings,bindings[1:]):
            if left['base']+max(1,left['size'])>right['base']:fail('overlapping native mappings '+left['key']+' and '+right['key'])
        if len({x['native_symbol'] for x in bindings})!=len(bindings):fail('duplicate native mapping symbol')
    end=max([base+limit]+[x['base']+max(1,x['size']) for x in bindings])
    if 'H' in layout:
        h=integer(layout['H'],'H')
        if h>=63 or 2**h<end:fail('H does not cover heap and mapped ranges')
    data=int(data_arg,0);text=int(text_arg,0) if text_arg else max(0x400000,(end+0x1fffff)&~0x1fffff)
    if data<4096 or data%4096 or data>base:fail('data base must be page aligned between null region and resolved heap')
    if text<end or text<=data or text%0x200000:fail('text must follow all device ranges on a 2MiB boundary')
    if any(x['base']<data for x in bindings):fail('mapped range precedes native data base')
    layout['native_bindings']=bindings
    (out/'resolved-layout.json').write_text(json.dumps(layout,sort_keys=True,separators=(',',':'))+'\n')
    (out/'native-layout.ll').write_text('target triple = "x86_64-unknown-linux-musl"\n'
        f'@__bennett_rt_native_layout = constant {{ i64, i64, i64 }} {{ i64 1, i64 {base}, i64 {limit} }}, align 8\n')
    def section(index,binding):
        name='.bennett_mapped_'+str(index);symbol=quoted(binding['native_symbol'])
        selection=' '.join(quoted(x) for x in binding['sections'])
        segment='native_data' if binding['base']<base else 'native_regions'
        return f''' {name} {binding['base']} : {{ *({selection}) }} :{segment}
 ASSERT(SIZEOF({name}) == {binding['size']}, "BD-E-NATIVE-LAYOUT: mapped section extent differs")
 ASSERT(DEFINED({symbol}), "BD-E-NATIVE-LAYOUT: mapped symbol is missing")
 ASSERT({symbol} == {binding['base']}, "BD-E-NATIVE-LAYOUT: mapped symbol address differs")
'''
    low=''.join(section(i,b) for i,b in enumerate(bindings) if b['base']<base)
    high=''.join(section(i,b) for i,b in enumerate(bindings) if b['base']>=base+limit)
    regions_header=' native_regions PT_LOAD FLAGS(6);' if high else ''
    (out/'comparison.ld').write_text(f'''PHDRS {{ native_data PT_LOAD FLAGS(6);{regions_header} native_text PT_LOAD FLAGS(5); }}
SECTIONS {{
 . = {data};
{low} __bennett_comparison_low_start = .;
{high} . = __bennett_comparison_low_start;
 .rodata : {{ *(.rodata .rodata.*) }} :native_data
 .data : {{ *(.data .data.*) *(.init_array*) *(.fini_array*) }} :native_data
 .bss : {{ *(.bss .bss.*) *(COMMON) }} :native_data
 __bennett_comparison_data_end = .;
 ASSERT(ALIGN(., 4096) == {base}, "BD-E-NATIVE-LAYOUT: native data end differs from resolved device heap base")
 . = {text}; .text : {{ *(.text .text.*) }} :native_text
 /DISCARD/ : {{ *(.eh_frame*) *(.comment) *(.note*) }}
}}
''')

try:
    if sys.argv[1]=='--audit':audit(*sys.argv[2:])
    else:prepare(*sys.argv[1:])
except (ValueError,KeyError,OSError,TypeError,IndexError,subprocess.TimeoutExpired) as error:
    print(str(error) if str(error).startswith('BD-E-') else 'BD-E-NATIVE-LAYOUT: '+str(error),file=sys.stderr)
    sys.exit(1)
