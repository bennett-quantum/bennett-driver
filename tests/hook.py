"""Check this repository's gate inputs and delegation stub.

The pinned gate tool's self-test owns hook protocol, worktree and isolation
behavior. This test neither invokes Git nor repeats those protocol fixtures.
"""
import hashlib
import os
import pathlib
import re
import subprocess
import tomllib

root = pathlib.Path(__file__).resolve().parents[1]
config = tomllib.loads((root / 'gate.toml').read_text())
assert config['schema'] == 1 and config['repo'] == root.name
assert re.fullmatch('[0-9a-f]{40}', config['tool_sha'])
assert 0 < config['timeout_s'] <= 7200
assert config['env']['CARGO_TARGET_DIR'].startswith('{root}/.tmp/')

required = {'bennett-conformance', 'bennett-runtimes', 'bennett-arith', 'bennett-plugin'}
assert required <= config['siblings'].keys()
for name, pin in config['siblings'].items():
    assert re.fullmatch('[0-9a-f]{40}', pin['sha']), name
assert any(check['argv'][:3] == ['cargo', 'test', '--offline'] for check in config['check'])
plugin = config['siblings']['bennett-plugin']
outputs = {name for build in plugin['build'] for name in build['outputs']}
assert {f'build/libbennett-plugin-{major}.so' for major in (18, 23)} <= outputs

# The gate must record and verify the published adapter used by native tests.
# Under isolation this path is the configured immutable runtime sibling.
runtime = config['siblings']['bennett-runtimes']
expected = runtime.get('files', {}).get('scripts/native-check')
assert expected, 'gate must bind the required published scripts/native-check adapter'
adapter = root.parent / 'bennett-runtimes/scripts/native-check'
assert adapter.is_file() and os.access(adapter, os.X_OK), adapter
assert hashlib.sha256(adapter.read_bytes()).hexdigest() == expected, adapter

stub = root / 'scripts/pre-push'
assert os.access(stub, os.X_OK), stub
subprocess.run(['bash', '-n', stub], check=True)
source = stub.read_text()
assert 'tools/gate_run.py' in source and '--tool-sha "$tool_sha"' in source
assert 'BENNETT_GATE_HOOK_PROBE' in source
assert 'cargo test' not in source, 'repository hook must delegate checks to the pinned gate'
print('Gate configuration, pinned runtime adapter, plugin build outputs and delegation stub verified')
