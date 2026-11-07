"""Run each fixture beside empty live sibling directories and the verified cache."""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import tomllib

root = pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'], prefix='driver-fixture-') as temp:
    workspace = pathlib.Path(temp)
    checkout = workspace / 'bennett-driver'
    for directory in ('tests', 'scripts'):
        shutil.copytree(root / directory, checkout / directory,
                        ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copyfile(root / 'gate.toml', checkout / 'gate.toml')
    (checkout / '.tmp/gate').mkdir(parents=True)
    (checkout / '.tmp/gate/cache').symlink_to(root / '.tmp/gate/cache', target_is_directory=True)
    for name in tomllib.loads((root / 'gate.toml').read_text())['siblings']:
        (workspace / name).mkdir()
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    # Inside the gate retain its verified layout. Bare local runs use the cache.
    result = subprocess.run(['python3', checkout / 'tests' / sys.argv[1], *sys.argv[2:]],
                            cwd=checkout, env=environment)
    raise SystemExit(result.returncode)
