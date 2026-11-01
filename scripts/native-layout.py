"""Read the device's resolved layout, never §14.9 block identities or defaults.

An explicit layout is a consumer adapter for already materialised modules.
Normal builds read each plugin launch object's authoritative layout section.
"""
import json, pathlib, sys
out, device, explicit, data_arg, text_arg = sys.argv[1:]
out, device = pathlib.Path(out), pathlib.Path(device)
def fail(message):
    raise ValueError('BD-E-NATIVE-LAYOUT: §19.5 '+message+'; bp-xyn / bennett-driver-cyg.3')
def integer(value, name):
    if type(value) is not int or not 0 <= value < 2**63: fail('invalid '+name)
    return value
try:
    if explicit:
        layout=json.loads(pathlib.Path(explicit).read_text())
    else:
        launches=device.parent/'launches.json'
        if not launches.is_file(): fail('missing resolved layout: supply --bennett-comparison-layout=FILE or adjacent launches.json')
        layouts=[]
        for entry in json.loads(launches.read_text()):
            text=(device.parent/entry['object']).read_text()
            if '\nsection layout\n' not in text: fail('launch has no resolved layout: '+entry['object'])
            layouts.append(json.loads(text.split('\nsection layout\n',1)[1].splitlines()[0]))
        if not layouts or any(x!=layouts[0] for x in layouts): fail('device entries lack one common resolved layout')
        layout=layouts[0]
    base=integer(layout['heap_base'],'heap_base');limit=integer(layout['heap_limit_max'],'heap_limit_max')
    if layout['null_size']!=4096 or layout['ptr_width']!=64: fail('native closure requires LP64 and 4096-byte null region')
    if base<4096 or base%4096 or base+limit>=2**63: fail('unaligned/overflowing heap range')
    end=base+limit
    # H bounds every device range, including arena and interface regions; using
    # the full address envelope keeps native code disjoint even for sparse maps.
    if 'H' in layout:
        h=integer(layout['H'],'H')
        if h>=63 or 2**h<end: fail('H does not cover heap')
        end=max(end,2**h)
    data=int(data_arg,0);text=int(text_arg,0) if text_arg else max(0x400000,(end+0x1fffff)&~0x1fffff)
    if data<4096 or data%4096 or data>base: fail('data base must be page aligned between null region and resolved heap')
    if text<end or text<=data or text%0x200000: fail('text must follow all device ranges on a 2MiB boundary')
    (out/'resolved-layout.json').write_text(json.dumps(layout,sort_keys=True,separators=(',',':'))+'\n')
    (out/'native-layout.ll').write_text('target triple = "x86_64-unknown-linux-musl"\n'
        f'@__bennett_rt_native_layout = constant {{ i64, i64, i64 }} {{ i64 1, i64 {base}, i64 {limit} }}, align 8\n')
    # Resolved global names are ISA symbols, not LLVM symbols; do not pretend
    # their placement is implemented. This check runs after the marker audit.
    unresolved = bool(layout['globals'] or layout['interface_regions'] or layout.get('arena'))
    mapping_assert = ' ASSERT(0, "BD-E-NATIVE-LAYOUT: bp-xyn must supply LLVM symbol to resolved device global/region mapping")' if unresolved else ''
    (out/'comparison.ld').write_text(f'''SECTIONS {{
{mapping_assert}
 . = {data}; .rodata : {{ *(.rodata .rodata.*) }}
 .data : {{ *(.data .data.*) *(.init_array*) *(.fini_array*) }}
 .bss : {{ *(.bss .bss.*) *(COMMON) }}
 __bennett_comparison_data_end = .;
 ASSERT(ALIGN(., 4096) == {base}, "BD-E-NATIVE-LAYOUT: native data end differs from resolved device heap base")
 . = {text}; .text : {{ *(.text .text.*) }}
 /DISCARD/ : {{ *(.eh_frame*) *(.comment) *(.note*) }}
}}
''')
except (ValueError,KeyError,OSError,TypeError,IndexError) as e:
    print(str(e) if str(e).startswith('BD-E-') else 'BD-E-NATIVE-LAYOUT: '+str(e),file=sys.stderr)
    sys.exit(1)
