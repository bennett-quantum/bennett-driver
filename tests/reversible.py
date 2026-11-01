import json, os, pathlib, subprocess, sys, tempfile
root = pathlib.Path(__file__).resolve().parents[1]
ws = root.parent
with tempfile.TemporaryDirectory(dir=root/'.tmp', prefix='rung3-') as temp:
    for m in (18,23):
        out = pathlib.Path(temp)/str(m)
        argv = [sys.argv[1], '--bennett-tier=reversible', '--bennett-entry=main',
                '-bennett-dialect=0.2.10', '-bennett-isa=0.8', f'--bennett-llvm-major={m}',
                '-bennett-out='+str(out), str(ws/'bennett-conformance/ladder/rung-3/fixtures/effect-console-r.ll')]
        p = subprocess.run(argv,capture_output=True)
        assert (out/'manifest.json').is_file(), p.stderr.decode()
        record = json.loads((out/'manifest.json').read_text())
        plugin = [c for c in record['commands'] if c['stage']=='plugin']
        assert plugin and '--bennett-tier=reversible' in plugin[0]['argv']
        assert '--bennett-entry=main' in plugin[0]['argv']
        if p.returncode:
            assert 'Unknown command line argument' in record['error'] or 'BLK-5' in record['error'] or 'BD-B-ISA7' in record['error'], record['error']
            print(f'LLVM {m}: real plugin refused R mode: {record["error"][:300]}')
        else:
            assert any(x['entry']=='main' for x in json.loads((out/'launches.json').read_text()))
            obj = (out/'main/launch.bennett').read_text()
            assert 'bennett.argv' in obj and 'effect console.write' in obj and 'fn r @' in obj
