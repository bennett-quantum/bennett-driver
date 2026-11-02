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
    # A runner that forbids Git can supply immutable published artifacts.
    # Require the exact evidence digest; this never changes expected launches.
    directory=os.environ.get('BENNETT_DRIVER_TEST_PUBLICATIONS')
    if directory:
        key={'bennett-runtimes':'runtimes','bennett-arith':'arith'}[repo]
        pin=json.loads((pathlib.Path(directory)/'manifest.json').read_text())[str(m)][key]
        assert pin['sha256']==digest, f'Explicit {repo} LLVM{m} pin differs from evidence'
        blob=pathlib.Path(pin['path']).read_bytes()
        assert hashlib.sha256(blob).hexdigest()==digest, f'Explicit publication changed: {pin["path"]}'
    else:
        # Historical regression publications are separate pinned sibling aliases.
        # Never search the live tree's Git history under gate isolation.
        blob=(WS/(repo+'-rung2')/relative).read_bytes()
    assert hashlib.sha256(blob).hexdigest()==digest, f'Pinned {repo} LLVM{m} publication differs: {digest}'
    path=pathlib.Path(job)/f'{repo}-{m}.bc'
    path.write_bytes(blob)
    assert sha(path)==digest
    return path

evidence = pathlib.Path(os.environ.get('BENNETT_RUNG2_EVIDENCE') or
    WS/'bennett-conformance/ladder/rung-2/evidence/driver-regression').resolve()
print(f'Rung-2 evidence: {evidence}', flush=True)
fixtures = WS/'bennett-conformance/ladder/rung-2/fixtures'
evidence_manifest = json.loads((evidence/'report.json').read_text())['manifest']
gate_config=tomllib.loads((ROOT/'gate.toml').read_text())
assert gate_config['siblings']['bennett-plugin']['sha']==evidence_manifest['plugin_commit'], 'gate plugin commit differs from frozen regression'
for name,digest in evidence_manifest['fixture_sha256'].items():
    assert sha(fixtures/name)==digest, f'Published rung-2 fixture changed: {name}'
with tempfile.TemporaryDirectory(prefix='integration-',dir=ROOT/'.tmp') as job:
    for m in (18,23):
        out = pathlib.Path(job)/str(m)
        # gate.toml builds this immutable sibling once per implementation SHA.
        # Build paths may change the .so bytes; the actual hash is still bound
        # into the driver manifest and certificate build record.
        plugin_source = pathlib.Path(os.environ.get('BENNETT_RUNG2_PLUGIN_DIR') or WS/'bennett-plugin/build')/f'libbennett-plugin-{m}.so'
        plugin = pathlib.Path(job)/f'plugin-{m}.so'
        shutil.copyfile(plugin_source, plugin)
        plugin_digest = sha(plugin)
        arith_digest=evidence_manifest['arith_sha256'][str(m)]
        arith = publication('bennett-arith',m,arith_digest,job)
        runtime_digest=evidence_manifest['runtimes_sha256'][str(m)]
        runtime = publication('bennett-runtimes',m,runtime_digest,job)
        expected_native = (evidence/str(m)/'native.txt').read_bytes()
        assert len(expected_native.splitlines())==10
        for executor in ('VM-forward','reference-forward'):
            assert (evidence/str(m)/(executor+'.txt')).read_bytes()==expected_native
        for entry in ('ht_demo_basic','ht_demo_grow'):
            assert (evidence/str(m)/'out'/entry/'launch.bennett').is_file()
        if '--check-inputs' in sys.argv[2:]:
            print(f'LLVM{m}: selected fixture/source/library hashes, executor bytes and pinned plugin selection verified',flush=True)
            continue
        run([EXE, f'--bennett-llvm-major={m}', '-bennett-dialect=0.2.10', '-bennett-isa=0.8',
             f'-bennett-out={out}', '-bennett-budget-default=10000000,1048576,65536,256,65536',
             '--bennett-analysis-budget-ms=300000',
             f'--bennett-runtimes={runtime}', f'--bennett-runtimes-sha256={runtime_digest}',
             f'--bennett-plugin={plugin}', f'--bennett-plugin-sha256={plugin_digest}',
             f'--bennett-arith={arith}', f'--bennett-arith-sha256={arith_digest}', fixtures/'hashtable_marked.c'])
        for name in ('linked.bc','postlink.bc','device.bc','host.bc','launches.json','manifest.json'):
            assert (out/name).is_file(), f'missing {name}'
        for entry in ('ht_demo_basic','ht_demo_grow'):
            expected = evidence/str(m)/'out'/entry/'launch.bennett'
            print(f'LLVM {m} {entry}: sha256={sha(out/entry/"launch.bennett")}', flush=True)
            assert sha(out/entry/'launch.bennett') == sha(expected), f'LLVM {m} {entry} hash differs: {evidence}'
        manifest = json.loads((out/'manifest.json').read_text())
        assert manifest['status'] == 'complete'
        assert manifest['llvm_major'] == m
        assert manifest['arith']['sha256'] == arith_digest
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
        for level in ('O0','O2'):
            baseline=pathlib.Path(job)/f'hosted-{m}-{level}'
            flags=['-O0','-fsanitize=address,undefined','-fno-omit-frame-pointer'] if level=='O0' else ['-O2']
            run([f'/usr/lib/llvm-{m}/bin/clang',*flags,fixtures/'hashtable.c',fixtures/'main_golden.c','-o',baseline])
            assert run([baseline]) == expected_native
        native_record = out/'native-comparison.json'
        p = subprocess.run([str(EXE), f'--bennett-llvm-major={m}',
            f'--bennett-materialised={out/"device.bc"}', f'--bennett-arith={arith}',
            f'--bennett-runtimes={WS}/bennett-runtimes/dist/llvm{m}/bennett-runtimes.bc',
            f'--bennett-native-input={fixtures/"main_golden.c"}',
            f'--bennett-comparison-record={native_record}'],capture_output=True)
        assert p.returncode != 0, 'unexpected native closure: audit then update this blocker regression'
        link = json.loads(native_record.read_text())
        assert link['materialised_sha256'] == sha(out/'device.bc')
        blockers = json.loads((out/'native-work/blockers.json').read_text())
        assert blockers[0]['code'] == 'BD-E-NATIVE-MARKERS', blockers
        error = blockers[0]['diagnostic']
        assert all(s in error for s in ('__bennett_qalloc','__bennett_qfree','bp-xyn')), error
        assert 'undefined reference to `main' not in error, error
        assert '__bennett_qalloc' in link['residual_markers']
        assert '__bennett_qfree' in link['residual_markers']
        assert '__bennett_rt_native_layout' in (out/'native-work/native-layout.ll').read_text()
        variants=json.loads((out/'native-work/native-comparisons.json').read_text())
        assert [v['variant'] for v in variants]==['O2','O0','O0-ASan']
        assert variants[2]['blocked_on']==['brt-nuu.2']
        print(f'LLVM {m}: driver native comparison blocked by residual qalloc/qfree (bp-xyn); recorded baselines agree', flush=True)
        print(f'LLVM {m}: both launch hashes agree with {evidence}', flush=True)
