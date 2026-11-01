import json, pathlib, subprocess, sys, tempfile
root=pathlib.Path(__file__).resolve().parents[1]
ws=root.parent
with tempfile.TemporaryDirectory(dir=root/'.tmp',prefix='comparison-') as tmp:
    for m in (18,23):
        d=pathlib.Path(tmp)/str(m);d.mkdir()
        # Diagnostic adapter: compile a tiny freestanding input to exercise the
        # auditable link independently of the blocked production R materialiser.
        src=d/'main.c';src.write_text('int main(void) { return 0; }\n')
        subprocess.run([f'/usr/lib/llvm-{m}/bin/clang','-emit-llvm','-c',str(src),'-o',str(d/'device.bc')],check=True)
        record=d/'native-comparison.json'
        p=subprocess.run([sys.argv[1],f'--bennett-llvm-major={m}',f'--bennett-materialised={d/"device.bc"}',
            f'--bennett-comparison-record={record}',f'--bennett-comparison-output={d/"native"}'],capture_output=True)
        assert record.is_file(),p.stderr.decode()
        r=json.loads(record.read_text());a=r['link_argv']
        assert r['llvm_major']==m
        assert all(x in a for x in ('-nostdlib','-nostdinc','-static','-no-pie'))
        assert all(str(ws/f'{lib}/dist/llvm{m}/{lib}.bc') in a for lib in ('bennett-runtimes','bennett-arith'))
        assert str(d/'device.bc') in a
        assert not any(x in a for x in ('-lc','-lm','-shared'))
        # No supplied runtime _start: it must refuse, never return a fake
        # successful binary with ld's default (incorrect) entry address.
        assert p.returncode!=0 and ('_start' in p.stderr.decode() or 'undefined' in p.stderr.decode()),p.stderr.decode()
        print(f'LLVM {m}: strict comparison refusal retained, link argv audited')
