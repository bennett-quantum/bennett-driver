"""Driver test inputs come from verified gate.toml checkouts."""
import hashlib, os, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from pinned_siblings import sibling


def configure(major):
    runtime = sibling('bennett-runtimes')
    arith = sibling('bennett-arith')
    paths = {
        'runtimes': runtime / f'dist/llvm{major}/bennett-runtimes.bc',
        'arith': arith / f'dist/llvm{major}/bennett-arith.bc',
        'plugin': sibling('bennett-plugin') / f'build/libbennett-plugin-{major}.so',
        'native-check': runtime / 'scripts/native-check',
        'native-support': runtime / f'dist/llvm{major}/musl-sysroot/lib/native-support.bc',
        'sysroot': runtime / f'dist/llvm{major}/musl-sysroot',
        'arith-generator': arith / 'softfloat/instantiate.py',
    }
    for key, path in paths.items():
        os.environ['BENNETT_DRIVER_' + key.upper().replace('-', '_')] = str(path)
    return paths


def flags(major, plugin=True):
    paths = configure(major)
    result=[]
    for key in (('plugin',) if plugin else ()) + ('runtimes', 'arith'):
        path = paths[key]
        result += [f'--bennett-{key}={path}',
                   f'--bennett-{key}-sha256=' + hashlib.sha256(path.read_bytes()).hexdigest()]
    return result

def target_headers(major):
    """Make test IR state the matching frontend ABI explicitly."""
    import subprocess
    result = subprocess.run([f'/usr/lib/llvm-{major}/bin/clang', '-x', 'c', '-',
        '-S', '-emit-llvm', '-o', '-'], input=b'int target_probe;\n', capture_output=True, check=True)
    return '\n'.join(line for line in result.stdout.decode().splitlines() if line.startswith('target '))+'\n'
