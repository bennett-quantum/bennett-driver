#!/usr/bin/env python3
"""Execute two audited domains; never load provider code into the component namespace."""
import hashlib
import json
import os
import pathlib
import subprocess
import signal
import sys
import uuid


failure_context={}

def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def checked(row):
    if sha(row['path']) != row['sha256']:
        raise ValueError('input SHA256 mismatch: '+row['path'])
    return row['path']


def validate_lifetime(lifetime,returncode):
    if lifetime['namespace'] == 0 or lifetime['binding_calls'] != 1 or lifetime['entry_calls'] != 1 or lifetime['unload_status'] != 0:
        raise ValueError('incomplete isolated live-program lifecycle')
    expected=-lifetime['signal'] if lifetime['signal'] else lifetime['status'] & 255
    if returncode!=expected:
        raise ValueError('bootstrap termination differs from the component outcome')


def execute():
    global failure_context
    executable = pathlib.Path(__file__).resolve()
    execution_id=uuid.uuid4().hex
    runtime=pathlib.Path(str(executable)+'.runtime.json')
    runtime.write_text(json.dumps(dict(status='running',execution_id=execution_id))+'\n')
    failure_context=dict(execution_id=execution_id)
    config_path = pathlib.Path(str(executable)+'.provider-config.json')
    if sha(config_path) != 'DRIVER_CONFIG_SHA256':
        raise ValueError('configuration SHA256 mismatch')
    config = json.loads(config_path.read_text())
    failure_context={k:config[k] for k in ('schema','provider','dependencies','bootstrap_dependencies','materialised_sha256','launch_sha256')}
    failure_context['execution_id']=execution_id
    inputs = {name:checked(row) for name,row in config['inputs'].items()}
    provider = checked(config['provider'])
    expected = {str(pathlib.Path(row['path']).resolve()):row['sha256'] for row in config['dependencies']}
    for row in config['dependencies']+config['bootstrap_dependencies']:
        checked(row)
    lifetime_path = executable.parent/(executable.name+'.lifetime-'+uuid.uuid4().hex+'.json')
    environment = {k:v for k,v in os.environ.items() if not k.startswith('LD_') and k != 'GLIBC_TUNABLES'}
    result = subprocess.run([inputs['bootstrap'], inputs['component'], provider, inputs['target'],
                             inputs['object'], str(lifetime_path), str(os.getpid()), str(executable), *sys.argv[1:]], env=environment)
    if not lifetime_path.is_file():
        raise ValueError('provider did not publish a completed lifetime (exit '+str(result.returncode)+')')
    lifetime = json.loads(lifetime_path.read_text())
    actual = {str(pathlib.Path(row['path']).resolve()) for row in lifetime['dependencies']}
    if actual != set(expected) or any(sha(path) != expected[path] for path in actual):
        raise ValueError('loaded provider dependency closure differs from audited closure')
    validate_lifetime(lifetime,result.returncode)
    receipt = dict(schema='bennett-driver-native-execution-1', execution_id=execution_id, profile=config['schema'],
                   materialised_sha256=config['materialised_sha256'], launch_sha256=config['launch_sha256'],
                   inputs=config['inputs'], provider=config['provider'], provider_dependencies=config['dependencies'],
                   bootstrap_dependencies=config['bootstrap_dependencies'], lifetime=lifetime,
                   exit_status=result.returncode)
    pathlib.Path(str(executable)+'.runtime.json').write_text(json.dumps(receipt,sort_keys=True)+'\n')
    if result.returncode < 0:
        signal.signal(-result.returncode,signal.SIG_DFL)
        os.kill(os.getpid(),-result.returncode)
    return result.returncode


def main():
    try:
        sys.exit(execute())
    except (ValueError,OSError,KeyError,subprocess.SubprocessError) as error:
        print('BD-E-NATIVE-PROVIDER: '+str(error),file=sys.stderr)
        pathlib.Path(str(pathlib.Path(__file__).resolve())+'.runtime.json').write_text(json.dumps(dict(failure_context,status='failed',error=str(error)))+'\n')
        sys.exit(125)

if __name__=='__main__':
    main()
