#!/usr/bin/env python3
"""Real external-tool regression against a frozen rung-2 evidence directory."""
import hashlib, json, os, pathlib, subprocess, sys, tempfile, tomllib
ROOT = pathlib.Path(__file__).resolve().parents[1]
WS = ROOT.parent
EXE = pathlib.Path(sys.argv[1]).resolve()
for name in ('DISPLAY','WAYLAND_DISPLAY','DBUS_SESSION_BUS_ADDRESS','BROWSER'):
    os.environ.pop(name, None)
os.environ['TMPDIR'] = str(ROOT/'.tmp')
(ROOT/'.tmp').mkdir(exist_ok=True)
def run(args):
    p = subprocess.run(list(map(str,args)), capture_output=True)
    assert p.returncode == 0, f'{args}\n{p.stdout.decode()}\n{p.stderr.decode()}'
    return p.stdout
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
evidence_root = WS/'bennett-conformance/.tmp/rung-2'
latest = pathlib.Path((evidence_root/'latest').read_text().strip())
# A later failed prerequisite run has native receipts but no objects. Compare the
# newest actual object receipts, explicitly recording that distinction.
complete = [p for p in sorted(evidence_root.iterdir(), reverse=True) if all(
    (p/str(m)/'out'/e/'launch.bennett').is_file()
    for m in (18,23) for e in ('ht_demo_basic','ht_demo_grow'))]
evidence = pathlib.Path(os.environ.get('BENNETT_RUNG2_EVIDENCE') or complete[0]).resolve()
print(f'Latest run: {latest}; latest object receipts: {evidence}', flush=True)
fixtures = WS/'bennett-conformance/ladder/rung-2/fixtures'
pins = tomllib.loads((WS/'bennett-plugin/SPEC_VERSIONS.toml').read_text())['arith']
with tempfile.TemporaryDirectory(prefix='integration-',dir=ROOT/'.tmp') as job:
    for m in (18,23):
        out = pathlib.Path(job)/str(m)
        # Consume the exact plugin-pinned publication, even when a sibling's
        # dirty dist is being rebuilt. Local git only; never change a sibling.
        digest = pins[f'llvm{m}_sha256']
        arith = pathlib.Path(pins[f'llvm{m}_path'])
        if sha(arith) != digest:
            for rev in run(['git','-C',WS/'bennett-arith','log','--all','--format=%H','--',f'dist/llvm{m}/bennett-arith.bc']).decode().split():
                blob = run(['git','-C',WS/'bennett-arith','show',f'{rev}:dist/llvm{m}/bennett-arith.bc'])
                if hashlib.sha256(blob).hexdigest() == digest:
                    arith = pathlib.Path(job)/f'arith-{m}.bc'
                    arith.write_bytes(blob)
                    break
            else: raise AssertionError(f'Pinned arith publication unavailable: {digest}')
        run([EXE, f'--bennett-llvm-major={m}', '-bennett-dialect=0.2.10', '-bennett-isa=0.8',
             f'-bennett-out={out}', '-bennett-budget-default=10000000,1048576,65536,256,65536',
             f'--bennett-arith={arith}', f'--bennett-arith-sha256={pins[f"llvm{m}_sha256"]}', fixtures/'hashtable_marked.c'])
        for name in ('linked.bc','postlink.bc','device.bc','host.bc','launches.json','manifest.json'):
            assert (out/name).is_file(), f'missing {name}'
        for entry in ('ht_demo_basic','ht_demo_grow'):
            expected = evidence/str(m)/'out'/entry/'launch.bennett'
            assert sha(out/entry/'launch.bennett') == sha(expected), f'LLVM {m} {entry} hash differs: {evidence}'
        manifest = json.loads((out/'manifest.json').read_text())
        assert manifest['status'] == 'complete'
        assert manifest['llvm_major'] == m
        assert manifest['arith']['sha256'] == pins[f'llvm{m}_sha256']
        assert manifest['plugin']['identity'] == 'dialect-0.2.10;isa-0.8'
        assert len(manifest['inputs']) == 1
        assert manifest['inputs'][0]['sha256'] == sha(fixtures/'hashtable_marked.c')
        record = json.loads((out/'build.json').read_text())
        digest = hashlib.sha256((out/'build.json').read_bytes().rstrip(b'\n')).hexdigest()
        assert (out/'build.sha256').read_text().strip() == digest
        for entry in ('ht_demo_basic','ht_demo_grow'):
            cert = json.loads((out/entry/'certificate.json').read_text())
            assert cert['producer']['version'] == '0.1.0+build.'+digest
            assert cert['producer']['materialisation']['pipeline'] == 'lto<O3>,bennett'
            receipt = json.loads((out/entry/'launch-record.json').read_text())
            for path, info in receipt['artifacts'].items():
                assert sha(out/path) == info['sha256'], path
        print(f'LLVM {m}: both launch hashes agree with {evidence}', flush=True)
