#!/usr/bin/env python3
"""Real external-tool regression against a frozen rung-2 evidence directory."""
import hashlib, json, os, pathlib, shutil, subprocess, sys, tempfile, tomllib
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
def publication(repo,m,digest,job):
    relative=f'dist/llvm{m}/{repo}.bc'
    blob=(WS/repo/relative).read_bytes()
    if hashlib.sha256(blob).hexdigest()!=digest:
        for rev in run(['git','-C',WS/repo,'log','--all','--format=%H','--',relative]).decode().split():
            candidate=run(['git','-C',WS/repo,'show',f'{rev}:{relative}'])
            if hashlib.sha256(candidate).hexdigest()==digest:
                blob=candidate
                break
        else: raise AssertionError(f'Pinned {repo} LLVM{m} publication unavailable: {digest}')
    path=pathlib.Path(job)/f'{repo}-{m}.bc'
    path.write_bytes(blob)
    assert sha(path)==digest
    return path

evidence_root = WS/'bennett-conformance/.tmp/rung-2'
latest = pathlib.Path((evidence_root/'latest').read_text().strip())
evidence = pathlib.Path(os.environ.get('BENNETT_RUNG2_EVIDENCE') or latest).resolve()
print(f'Rung-2 evidence: {evidence}', flush=True)
fixtures = WS/'bennett-conformance/ladder/rung-2/fixtures'
evidence_manifest = json.loads((evidence/'report.json').read_text())['manifest']
with tempfile.TemporaryDirectory(prefix='integration-',dir=ROOT/'.tmp') as job:
    for m in (18,23):
        out = pathlib.Path(job)/str(m)
        command = next(c for c in evidence_manifest['commands'] if c['tag']==f'{m}/production')
        plugin_source = pathlib.Path(next(a.split('=',1)[1] for a in command['argv'] if a.startswith('-load-pass-plugin=')))
        plugin = pathlib.Path(job)/f'plugin-{m}.so'
        shutil.copyfile(plugin_source, plugin)
        plugin_digest = evidence_manifest['plugin_sha256'][str(m)]
        assert sha(plugin) == plugin_digest, f'Frozen evidence plugin changed: {plugin_source}'
        pins = tomllib.loads((plugin_source.parent.parent/'SPEC_VERSIONS.toml').read_text())['arith']
        # Snapshot exact published bytes; never race a sibling rebuild.
        arith = publication('bennett-arith',m,pins[f'llvm{m}_sha256'],job)
        runtime_digest=evidence_manifest['runtimes_sha256'][str(m)]
        runtime = publication('bennett-runtimes',m,runtime_digest,job)
        run([EXE, f'--bennett-llvm-major={m}', '-bennett-dialect=0.2.10', '-bennett-isa=0.8',
             f'-bennett-out={out}', '-bennett-budget-default=10000000,1048576,65536,256,65536',
             '--bennett-analysis-budget-ms=300000',
             f'--bennett-runtimes={runtime}', f'--bennett-runtimes-sha256={runtime_digest}',
             f'--bennett-plugin={plugin}', f'--bennett-plugin-sha256={plugin_digest}',
             f'--bennett-arith={arith}', f'--bennett-arith-sha256={pins[f"llvm{m}_sha256"]}', fixtures/'hashtable_marked.c'])
        for name in ('linked.bc','postlink.bc','device.bc','host.bc','launches.json','manifest.json'):
            assert (out/name).is_file(), f'missing {name}'
        for entry in ('ht_demo_basic','ht_demo_grow'):
            expected = evidence/str(m)/'out'/entry/'launch.bennett'
            print(f'LLVM {m} {entry}: sha256={sha(out/entry/"launch.bennett")}', flush=True)
            assert sha(out/entry/'launch.bennett') == sha(expected), f'LLVM {m} {entry} hash differs: {evidence}'
        manifest = json.loads((out/'manifest.json').read_text())
        assert manifest['status'] == 'complete'
        assert manifest['llvm_major'] == m
        assert manifest['arith']['sha256'] == pins[f'llvm{m}_sha256']
        assert manifest['plugin']['sha256'] == plugin_digest
        assert manifest['plugin']['identity'] == 'dialect-0.2.10;isa-0.8'
        assert len(manifest['inputs']) == 1
        assert manifest['inputs'][0]['sha256'] == sha(fixtures/'hashtable_marked.c')
        record = json.loads((out/'build.json').read_text())
        digest = hashlib.sha256((out/'build.json').read_bytes().rstrip(b'\n')).hexdigest()
        assert (out/'build.sha256').read_text().strip() == digest
        for entry in ('ht_demo_basic','ht_demo_grow'):
            cert = json.loads((out/entry/'certificate.json').read_text())
            assert cert['bindings']['dialect_mapping_version'] == '0.2.9'
            assert cert['producer']['materialisation']['normaliser_version'] == '0.2.8'
            assert cert['producer']['version'] == '0.1.0+build.'+digest
            assert cert['producer']['materialisation']['pipeline'] == 'lto<O3>,bennett'
            receipt = json.loads((out/entry/'launch-record.json').read_text())
            for path, info in receipt['artifacts'].items():
                assert sha(out/path) == info['sha256'], path
        # Compare recorded native O0/sanitizer and O2 observations, then attempt
        # the driver's stricter same-materialised-module comparison. The latter
        # must not silently reuse these hosted baseline binaries.
        expected_native = (evidence/str(m)/'native.txt').read_bytes()
        for level in ('O0','O2'):
            assert run([evidence/str(m)/f'native-{level}']) == expected_native
        native_record = out/'native-comparison.json'
        p = subprocess.run([str(EXE), f'--bennett-llvm-major={m}',
            f'--bennett-materialised={out/"device.bc"}', f'--bennett-arith={arith}',
            f'--bennett-runtimes={runtime}',
            f'--bennett-native-input={fixtures/"main_golden.c"}',
            f'--bennett-comparison-record={native_record}'],capture_output=True)
        assert p.returncode != 0, 'unexpected native closure: audit then update this blocker regression'
        link = json.loads(native_record.read_text())
        assert link['materialised_sha256'] == sha(out/'device.bc')
        blockers = json.loads((out/'native-work/blockers.json').read_text())
        assert blockers[0]['code'] == 'BD-E-NATIVE-LINK', blockers
        error = blockers[0]['diagnostic']
        assert 'undefined reference' in error and any(s in error for s in ('printf','__bennett_nz_alloc','__bennett_qalloc')), error
        print(f'LLVM {m}: driver native comparison blocked by unpublished closure; recorded O0/O2 baselines agree', flush=True)
        print(f'LLVM {m}: both launch hashes agree with {evidence}', flush=True)
