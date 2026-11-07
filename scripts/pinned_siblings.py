"""Resolve this repository's siblings only through its gate.toml pins."""
import os
from pathlib import Path
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def head(directory):
    """Detached gate worktrees need no Git process; live refs use read-only Git."""
    try:
        metadata = directory / '.git'
        if metadata.is_file():
            metadata = directory / metadata.read_text().strip().removeprefix('gitdir: ')
        value = (metadata / 'HEAD').read_text().strip()
        if len(value) == 40 and all(c in '0123456789abcdef' for c in value):
            return value
        result = subprocess.run(['git', '-C', str(directory), 'rev-parse', 'HEAD'],
                                capture_output=True, text=True, timeout=10)
        return result.stdout.strip() if result.returncode == 0 else 'unavailable'
    except (OSError, subprocess.TimeoutExpired):
        return 'unavailable'


def sibling(name):
    pins = tomllib.loads((ROOT / 'gate.toml').read_text())['siblings']
    if name not in pins:
        raise SystemExit(f'BD-E-SIBLING-PIN: {name} has no gate.toml pin')
    sha = pins[name]['sha']
    layout = os.environ.get('BENNETT_GATE_LAYOUT')
    path = (Path(layout) / name if layout else
            ROOT / '.tmp/gate/cache' / f'{name}@{sha[:12]}' / name)
    actual = head(path)
    if not path.is_dir() or actual != sha:
        live = head(ROOT.parent / pins[name].get('repo', name))
        raise SystemExit(f'BD-E-SIBLING-PIN: {name} pinned {sha}; {path} HEAD {actual} '
                         f'(missing or mismatch); live ../{pins[name].get("repo", name)} HEAD {live}; '
                         f'materialise with gate_run.py verify --repo {ROOT} --sha HEAD')
    return path
