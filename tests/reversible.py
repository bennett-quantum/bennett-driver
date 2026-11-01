import json, os, pathlib, subprocess, sys, tempfile
from toolchain import flags
root = pathlib.Path(__file__).resolve().parents[1]
ws = root.parent
with tempfile.TemporaryDirectory(dir=root/'.tmp', prefix='rung3-') as temp:
    for m in (18,23):
        out = pathlib.Path(temp)/str(m)
        argv = [sys.argv[1], '--bennett-tier=reversible', '--bennett-entry=main',
                '-bennett-dialect=0.2.10', '-bennett-isa=0.8', f'--bennett-llvm-major={m}',
                '-bennett-out='+str(out), str(ws/'bennett-conformance/ladder/rung-3/fixtures/effect-console-r.ll')]
        argv[1:1]=flags(m)
        p = subprocess.run(argv,capture_output=True)
        assert (out/'manifest.json').is_file(), p.stderr.decode()
        record = json.loads((out/'manifest.json').read_text())
        plugin = [c for c in record['commands'] if c['stage']=='plugin']
        assert plugin and '--bennett-tier=reversible' in plugin[0]['argv']
        assert '--bennett-entry=main' in plugin[0]['argv']
        if p.returncode:
            reports=json.loads((out/'blockers.json').read_text())
            if reports[0]['code']=='BD-B-ISA7':
                assert record['status']=='blocked',record
                assert (out/'build.json').is_file(), 'blocked production still requires build metadata'
            else:
                assert reports[0]['code']=='DRIVER-PLUGIN-REFUSAL', reports
                assert reports[1]['code']=='BD-B-ISA7', reports
                assert 'Unknown command line argument' in record['error'],record['error']
                print(f'LLVM {m}: real plugin lacks R mode: {record["error"][:300]}')
                continue
        assert any(x['entry']=='main' for x in json.loads((out/'launches.json').read_text()))
        obj = (out/'main/launch.bennett').read_text()
        assert 'bennett.argv' in obj and 'effect console.write' in obj and 'fn r @' in obj
        for f in ('device.bc','host.bc','main/build.json','main/certificate.json','main/coverage.json','main/blockers.json','main/launch-record.json'):
            assert (out/f).is_file(),f
        replies=json.loads((out/'main/argv-replies.json').read_text())
        assert replies==[dict(service='bennett.argv',payload='00'*20,reply='00'*20)]
        print(f'LLVM {m}: R argv/console launch emitted; verdict {record["status"]}')
