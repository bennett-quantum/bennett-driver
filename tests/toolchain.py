"""Optional explicit immutable artifacts for tests during sibling rebuilds."""
import json, os, pathlib
def flags(major, plugin=True):
    directory=os.environ.get('BENNETT_DRIVER_TEST_ARTIFACTS')
    if not directory: return []
    pin=json.loads((pathlib.Path(directory)/'manifest.json').read_text())[str(major)]
    result=[]
    if plugin: result += ['--bennett-plugin='+pin['path'], '--bennett-plugin-sha256='+pin['sha256']]
    for key in ('runtimes','arith'):
        result += [f'--bennett-{key}='+pin[key]['path'],f'--bennett-{key}-sha256='+pin[key]['sha256']]
    return result
