"""Real process init/fini registrations keep storage, ordering and cleanup."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from contextlib import nullcontext
from toolchain import configure,sibling

SOURCE='''#include <stdio.h>
#include <stdlib.h>
static int state;
static void from_ctor(void) { putchar('Z'); }
__attribute__((constructor(202))) static void later1(void) { state=state*10+2; putchar('B'); }
__attribute__((constructor(101))) static void earlier(void) { state=state*10+1; putchar('A'); atexit(from_ctor); }
__attribute__((constructor(202))) static void later2(void) { state=state*10+3; putchar('C'); }
__attribute__((destructor(202))) static void fini1(void) { putchar('b'); }
__attribute__((destructor(101))) static void fini0(void) { putchar('a'); }
__attribute__((destructor(202))) static void fini2(void) { putchar('c'); }
static void first(void) { putchar('X'); }
static void second(void) { putchar('Y'); }
int main(void) { if(state!=123) return 83; putchar('M'); atexit(first); atexit(second); return 7; }
'''
EXPECTED=b'ABCMYXZcba'


def run(argv,expected=0,**kwargs):
    process=subprocess.Popen(list(map(str,argv)),stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,**kwargs)
    try:stdout,stderr=process.communicate(timeout=180)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid,signal.SIGKILL);process.communicate()
        raise AssertionError('UNKNOWN: init/fini execution guard180s')
    assert process.returncode==expected,(process.returncode,stderr.decode()[-5000:])
    return stdout


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def common(binary,major,source,out,paths):
    return [binary,f'--bennett-llvm-major={major}','-bennett-dialect=0.3-r1','-bennett-isa=0.9',
        '--bennett-tier=reversible','--bennett-entry=main','--bennett-layout-data-base=65536',
        f'--bennett-out={out}',f'--bennett-plugin={sibling("bennett-plugin-r-contract")}/build/libbennett-plugin-{major}.so',
        *[f'--bennett-{key}={paths[key]}' for key in ('runtimes','arith','sysroot')],
        '-bennett-budget-default=10000000,1048576,65536,256,65536',source]


def run_major(binary,directory,major):
    paths=configure(major);llvm=Path(f'/usr/lib/llvm-{major}/bin')
    source=directory/f'callbacks-{major}.c';source.write_text(SOURCE)
    prepared=directory/f'prepared-{major}'
    run([*common(binary,major,source,prepared,paths),'--bennett-emit=process-bitcode'])
    report_path=prepared/'process-init-fini.json'
    assert report_path.is_file(),'driver did not bind the real init/fini registration arrays'
    report=json.loads(report_path.read_text());tables={r['kind']:r for r in report['tables']}
    assert [r['priority'] for r in tables['init']['entries']]==[101,202,202],tables
    assert [r['function'] for r in tables['init']['entries']]==['earlier','later1','later2'],tables
    assert [r['function'] for r in tables['fini']['entries']]==['fini0','fini1','fini2'],tables
    assert tables['fini']['end_offset']-tables['fini']['start_offset']==3*8,tables
    ir=run([llvm/'llvm-dis',prepared/'process-prepared.bc','-o','-']).decode()
    assert '@llvm.global_ctors =' not in ir and '@llvm.global_dtors =' not in ir
    assert '@__fini_array_end = ' in ir and ' alias ' in next(line for line in ir.splitlines() if line.startswith('@__fini_array_end ='))
    out=directory/f'full-{major}'
    run([*common(binary,major,source,out,paths),'--bennett-comparison=true',
        f'--bennett-native-provider={sibling("bennett-native-provider")}/target/debug/libbennett_vm.so',
        f'--bennett-native-target={sibling("bennett-native-targets")}/targets/ideal-all-to-all.json'])
    preparation=json.loads((out/'native-preparation.json').read_text())
    linked=json.loads((out/'process-init-fini.json').read_text())
    mapping=preparation['device_globals']
    for level in ('O0','O2'):
        symbols={row.split()[-1]:int(row.split()[0],16) for row in
                 run([llvm/'llvm-nm','--defined-only',out/f'native-{level}.component']).decode().splitlines() if len(row.split())==3}
        for table in linked['tables']:
            slot=next(row for row in mapping.values() if row['source_key']=='name:'+table['storage'])
            assert symbols[slot['native_symbol']]==slot['base'],(table,slot)
            for boundary in ('start','end'):
                name=f"__{table['kind']}_array_{boundary}"
                assert symbols[name]==slot['base']+table[boundary+'_offset'],(name,symbols[name],slot,table)
    run([directory/'reference-init-fini',out/'main/launch.bennett',out/'main/argv-replies.json',EXPECTED.decode()])
    before={p:sha(p) for p in (out/'main').rglob('*') if p.is_file()}
    for level in ('O0','O2'):
        assert run([out/('native-'+level)],7)==EXPECTED
        life=json.loads(Path(str(out/('native-'+level))+'.runtime.json').read_text())['lifetime']
        assert life['load'] and life['binding_calls']==1 and life['entry_calls']==1 and life['unload_status']==0,life
    assert {p:sha(p) for p in (out/'main').rglob('*') if p.is_file()}==before
    print(f'LLVM{major}: actual ctor/fini arrays, priority/order and registered cleanup; native O0/O2 exact output/status')


def check_link_inventory(binary,directory,major):
    paths=configure(major);llvm=Path(f'/usr/lib/llvm-{major}/bin')
    source=directory/f'sections-{major}.ll'
    # Duplicate callbacks are intentional. Distinct section objects must retain
    # their own offsets even when their first callback is the same function.
    from toolchain import target_headers
    source.write_text(target_headers(major)+r''' 
@p = global [1 x ptr] [ptr @pre], section ".preinit_array"
@x = global [2 x ptr] [ptr @a, ptr @b], section ".init_array.00202"
@y = global [1 x ptr] [ptr @a], section ".init_array.00202"
@z = global [0 x ptr] zeroinitializer, section ".fini_array"
@llvm.global_ctors = appending global [1 x {i32, ptr, ptr}] [{i32, ptr, ptr} {i32 101, ptr @b, ptr null}]
define void @pre() { ret void }
define void @a() { ret void }
define void @b() { ret void }
define i32 @main() { ret i32 7 }
''')
    out=directory/f'sections-{major}'
    run([*common(binary,major,source,out,paths),'--bennett-emit=process-bitcode'])
    tables={r['kind']:r for r in json.loads((out/'process-init-fini.json').read_text())['tables']}
    assert [r['function'] for r in tables['init']['entries']]==['b','a','b','a'],tables
    ir=run([llvm/'llvm-dis',out/'process-prepared.bc','-o','-']).decode()
    aliases={line.split(' =')[0]:line for line in ir.splitlines() if ' alias ' in line}
    assert '@x' in aliases and '@y' in aliases and '@z' in aliases,aliases
    assert 'i64 1)' in aliases['@x'] and 'i64 3)' in aliases['@y'],aliases
    assert tables['fini']['entries']==[] and tables['fini']['start_offset']==tables['fini']['end_offset'],tables
    assert not any('section ".init_array' in line or 'section ".fini_array' in line for line in ir.splitlines())
    # No registrations is an audited zero extent, with no invented array storage.
    empty=directory/f'empty-{major}.c';empty.write_text('int main(void) { return 7; }')
    out=directory/f'empty-{major}'
    run([*common(binary,major,empty,out,paths),'--bennett-emit=process-bitcode'])
    for table in json.loads((out/'process-init-fini.json').read_text())['tables']:
        assert not table['entries'] and table['start_offset']==table['end_offset']==8,table
        assert table['storage'].startswith('.bennett.driver.empty.argv'),table
    print(f'LLVM{major}: real section views, duplicate callbacks and empty link locations')


def check_comdat(binary,directory,major):
    from toolchain import target_headers
    unit=target_headers(major)+r'''
$chosen = comdat any
@chosen = linkonce_odr global i32 0, comdat
@llvm.global_ctors = appending global [1 x {i32, ptr, ptr}] [{i32, ptr, ptr} {i32 101, ptr @selected, ptr @chosen}]
define linkonce_odr void @selected() comdat($chosen) { ret void }
'''
    sources=[directory/f'comdat-{major}-{i}.ll' for i in range(2)]
    sources[0].write_text(unit+'define i32 @main() { ret i32 7 }\n')
    sources[1].write_text(unit)
    out=directory/f'comdat-{major}'
    run([*common(binary,major,sources[0],out,configure(major)),sources[1],'--bennett-emit=process-bitcode'])
    table=next(r for r in json.loads((out/'process-init-fini.json').read_text())['tables'] if r['kind']=='init')
    assert len(table['entries'])==1,table
    assert table['entries'][0]['associated']=='chosen',table
    print(f'LLVM{major}: actual LLVM COMDAT selection retained exactly once')


def main():
    evidence=os.environ.get('BENNETT_DRIVER_INIT_FINI_EVIDENCE')
    if evidence:Path(evidence).mkdir(parents=True,exist_ok=False)
    with (nullcontext(evidence) if evidence else tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'],prefix='init-fini-')) as temp:
        directory=Path(temp)
        release=sibling('bennett-isa-spec-review')/'reference-interpreter/target/release'
        run(['rustc','--edition=2021','-O',Path(__file__).parent/'fixtures/init_fini_reference.rs',
             '-L',f'dependency={release / "deps"}','--extern',f'bennett_isa_ref={release / "libbennett_isa_ref.rlib"}',
             '-o',directory/'reference-init-fini'])
        for major in (18,23):
            check_link_inventory(sys.argv[1],directory,major)
            check_comdat(sys.argv[1],directory,major)
            run_major(sys.argv[1],directory,major)


if __name__ == "__main__":
    main()
