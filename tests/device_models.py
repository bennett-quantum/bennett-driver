"""Real descriptor-to-model prologue acceptance, independent of runtime tests."""
import hashlib, json, os, pathlib, subprocess, sys, tempfile
from contextlib import nullcontext
from toolchain import flags, configure, sibling
root = pathlib.Path(__file__).resolve().parents[1]
plugin_root = sibling('bennett-plugin-native-comparison')
evidence = os.environ.get('BENNETT_DRIVER_DEVICE_EVIDENCE')
if evidence:
    pathlib.Path(evidence).mkdir(parents=True, exist_ok=False)
with (nullcontext(evidence) if evidence else tempfile.TemporaryDirectory(dir=root/'.tmp', prefix='device-models-')) as temp:
    d = pathlib.Path(temp)
    header = sibling('bennett-dialect-spec')/'spec/bennett_markers.h'
    source = d/'clock.c'
    source.write_text((root/'tests/fixtures/device_clock.c').read_text().replace('"bennett_markers.h"', '"'+str(header)+'"'))
    reference = sibling('bennett-isa-spec-review')/'reference-interpreter/target/release/bennett-isa-ref'
    for major in (18, 23):
        configure(major)
        out = d/f'out-{major}'
        plugin = plugin_root/f'build/libbennett-plugin-{major}.so'
        result = subprocess.run([sys.argv[1], *flags(major, plugin=False), f'--bennett-plugin={plugin}',
            '--bennett-plugin-sha256='+hashlib.sha256(plugin.read_bytes()).hexdigest(),
            f'--bennett-llvm-major={major}', '--bennett-dialect=0.2.13', f'--bennett-out={out}', str(source)],
            capture_output=True, timeout=120)
        assert result.returncode == 0, result.stderr.decode()
        obj = out/'top/launch.bennett'
        result = subprocess.run([reference, 'run-program', obj, 'top', '--budget', '1000000,1048576,65536,256'],
            capture_output=True, timeout=120)
        assert result.returncode == 0, result.stderr.decode()
        value = json.loads(result.stdout)
        assert value['status'] == 'COMPLETED' and value['fault'] is None and not value['faults'], value
        assert value['results'] == [{'type': 'i32', 'value': '67'}], value
        assert value['run_state'] == 'CLOSED' and not value['host_requests'], value
        assert value['tape'] == [], 'L clock is ordinary reversible state, not an R tape'
    print('Both majors: descriptor CLOCK(3) reads3/4, repeated oracle starts fresh, registers clean, no host call/second tape')
