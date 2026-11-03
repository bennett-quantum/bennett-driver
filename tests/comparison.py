"""Native support adapter diagnostics; these are NOT plugin acceptance tests."""
import hashlib, json, pathlib, subprocess, sys, tempfile
root=pathlib.Path(__file__).resolve().parents[1]
ws=root.parent
def run(args):
    p=subprocess.run(list(map(str,args)),capture_output=True)
    assert p.returncode==0,p.stderr.decode()
    return p.stdout
with tempfile.TemporaryDirectory(dir=root/'.tmp',prefix='comparison-') as tmp:
    for m in (18,23):
        d=pathlib.Path(tmp)/str(m);d.mkdir()
        llvm=pathlib.Path(f'/usr/lib/llvm-{m}/bin')
        # No marker, no materialiser substitution: a diagnostic already-materialised
        # primitive consumer exercises the closure/table/strict link in isolation.
        src=d/'main.c';src.write_text('extern void *__bennett_nz_alloc(unsigned long); extern void __bennett_nz_free(void *); int main(void) { volatile unsigned char *p=__bennett_nz_alloc(1); extern const unsigned long __bennett_rt_native_layout[3]; if ((unsigned long)p != __bennett_rt_native_layout[1] || *p) return 1; *p=42; __bennett_nz_free((void *)p); return 0; }\n')
        run([llvm/'clang','-emit-llvm','-c',src,'-o',d/'device.bc'])
        layout=d/'layout.json'
        layout.write_text(json.dumps(dict(null_size=4096,ptr_width=64,heap_base=69632,heap_limit_max=1048576,globals={},interface_regions={})))
        out=d/'out'
        args=[sys.argv[1],f'--bennett-llvm-major={m}',f'--bennett-materialised={d/"device.bc"}',f'--bennett-out={out}',f'--bennett-comparison-layout={layout}','--bennett-layout-data-base=65536']
        run(args)
        records=json.loads((out/'native-comparisons.json').read_text())
        assert [r['status'] for r in records]==['linked','linked','blocked'],records
        assert records[2]['blocked_on']==['brt-nuu.2']
        table=(out/'native-layout.ll').read_text()
        assert '@__bennett_rt_native_layout = constant { i64, i64, i64 } { i64 1, i64 69632, i64 1048576 }, align 8' in table
        for level in ('O0','O2'):
            r=next(r for r in records if r.get('variant')==level)
            a=r['link_argv'];assert all(x in a for x in ('-nostdlib','-nostdinc','-static','-no-pie'))
            obj=pathlib.Path(r['codegen_object']['path'])
            assert hashlib.sha256(obj.read_bytes()).hexdigest()==r['codegen_object']['sha256']
            assert r['provenance']=='explicit module; producer receipt not verified'
            assert not any(x in a for x in ('-lc','-lm','-fsanitize=address,undefined'))
            assert run([out/f'native-{level}'])==b''
            assert not run([llvm/'llvm-nm','--undefined-only',out/f'native-{level}']).strip()
            assert b'INTERP' not in run(['readelf','-l',out/f'native-{level}'])
        manifest=json.loads((out/'manifest.json').read_text())
        stages=[c['stage'] for c in manifest['commands']]
        assert stages.index('comparison-bitcode-link') < stages.index('comparison-support-link') < stages.index('comparison-closure-link')
        assert records[0]['native_support_sha256']==hashlib.sha256((ws/f'bennett-runtimes/dist/llvm{m}/musl-sysroot/lib/native-support.bc').read_bytes()).hexdigest()
        # Retain an explicit harness main before --only-needed closes startup.
        src.write_text(src.read_text().replace('int main(void)', 'int check(void)'))
        run([llvm/'clang','-emit-llvm','-c',src,'-o',d/'callee.bc'])
        harness=d/'harness.c';harness.write_text('extern int check(void); int main(void) { return check(); }')
        adapted=d/'harness-out'
        run([sys.argv[1],f'--bennett-llvm-major={m}',f'--bennett-materialised={d/"callee.bc"}',f'--bennett-native-input={harness}',f'--bennett-out={adapted}',f'--bennett-comparison-layout={layout}','--bennett-layout-data-base=65536'])
        for level in ('O0','O2'): assert run([adapted/f'native-{level}'])==b''
        # A materialised callee must see the real extent of harness globals.
        # They belong to the comparison's object metadata, even though the
        # harness is added only after producer materialisation has been fixed.
        consumer=d/'consumer.ll'
        consumer.write_text('define i32 @inspect(ptr %p) { %v = load i8, ptr %p\n %n = zext i8 %v to i32\n ret i32 %n }\n')
        harness.write_text('extern int inspect(const void *); unsigned char input=7; int main(void) { return inspect(&input)!=7; }')
        global_out=d/'harness-global-out'
        run([sys.argv[1],f'--bennett-llvm-major={m}',f'--bennett-materialised={consumer}',f'--bennett-native-input={harness}',f'--bennett-out={global_out}',f'--bennett-comparison-layout={layout}','--bennett-layout-data-base=65536'])
        for level in ('O0','O2'): assert run([global_out/f'native-{level}'])==b''
        # H is the device address envelope, not the end of occupied ranges.
        # The exact first 2MiB boundary above data+heap is 0x600000, not 2^H.
        large=d/'large.json';large.write_text(json.dumps(json.loads(layout.read_text())|{'heap_limit_max':4194304,'H':23}))
        large_out=d/'large-out'
        run([sys.argv[1],f'--bennett-llvm-major={m}',f'--bennett-materialised={d/"device.bc"}',f'--bennett-out={large_out}',f'--bennett-comparison-layout={large}','--bennett-layout-data-base=65536'])
        assert '. = 6291456; .text' in (large_out/'comparison.ld').read_text()
        # Layout errors must never silently relocate heap or overlap code.
        for label,change,extra in (
            ('heap-mismatch',{'heap_base':73728},[]),
            ('globals',{'globals':{'G1':{'base':65536,'size':1,'image':'G1'}}},[]),
            ('text-overlap',{},['--bennett-layout-text-base=0x0']),
            ('overflow',{'heap_limit_max':2**63},[])):
            invalid=d/(label+'.json'); invalid.write_text(json.dumps(json.loads(layout.read_text())|change))
            p=subprocess.run([sys.argv[1],f'--bennett-llvm-major={m}',f'--bennett-materialised={d/"device.bc"}',f'--bennett-out={d/label}',f'--bennett-comparison-layout={invalid}','--bennett-layout-data-base=65536',*extra],capture_output=True)
            assert p.returncode and 'BD-E-NATIVE-LAYOUT' in p.stderr.decode(),p.stderr.decode()
        # No inferred/default heap and no use of §14.9 block identity.
        missing=d/'missing';p=subprocess.run([*args[:3],f'--bennett-out={missing}'],capture_output=True)
        assert p.returncode and 'BD-E-NATIVE-LAYOUT' in p.stderr.decode(),p.stderr.decode()
        print(f'LLVM {m}: support merge/table and plain O0/O2 diagnostic execution; sanitizer explicitly blocked')
