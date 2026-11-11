#!/usr/bin/env python3
"""Attach a canonical driver build record without changing ISA object bytes."""
import hashlib, json, pathlib, struct, sys
def load(p): return json.loads(p.read_text())
def canonical(value): return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p, value): p.write_bytes(canonical(value) + b'\n')
def argument_check(condition, message):
    if not condition:
        raise ValueError('BD-E-PROCESS-ARGS: '+message)

def argument_hex(value):
    argument_check(isinstance(value,str), 'reply/argument hex must be a string')
    try:
        data=bytes.fromhex(value)
    except ValueError as error:
        raise ValueError('BD-E-PROCESS-ARGS: invalid hexadecimal bytes') from error
    argument_check(len(value)==2*len(data), 'hex bytes must be contiguous')
    return data

def argument_string(value):
    if isinstance(value,str):
        data=value.encode('utf-8')
    else:
        argument_check(isinstance(value,dict) and set(value)=={'hex'}, 'expected a string or {hex: bytes}')
        data=argument_hex(value['hex'])
    argument_check(b'\0' not in data, 'native argument strings cannot contain NUL')
    return data

def argument_context(manifest):
    if 'process_arguments' not in manifest:return [],[]
    artifact=manifest['process_arguments']
    path=pathlib.Path(artifact['path'])
    argument_check(sha(path)==artifact['sha256'], 'process input SHA256 changed during build')
    context=load(path)
    argument_check(context.get('schema')=='bennett-driver-process-arguments-1', 'unsupported process input schema')
    argv,envp=context['argv'],context['envp']
    argument_check(isinstance(argv,list) and isinstance(envp,list), 'argv and envp must be arrays')
    argument_check(len(argv)<2**31, 'argc is outside the nonnegative C int range')
    return [argument_string(x) for x in argv],[argument_string(x) for x in envp]

def argument_payload(width,argv,envp):
    argument_check(width in (32,64), 'unsupported target pointer width')
    pointer=width//8
    table=bytearray((len(argv)+len(envp)+2)*pointer)
    strings=bytearray()
    for index,value in enumerate(argv+[None]+envp+[None]):
        if value is None:continue
        offset=24+len(table)+len(strings)
        table[index*pointer:(index+1)*pointer]=offset.to_bytes(pointer,'little')
        strings.extend(value+b'\0')
    size=24+len(table)+len(strings)
    argument_check(size<2**width, 'argument payload does not fit target address width')
    return struct.pack('<IIQQ',len(argv),0,len(envp),size)+table+strings

def validate_argument_payload(payload,width):
    argument_check(len(payload)>=24, 'short argument header')
    argc,reserved,envc,size=struct.unpack_from('<IIQQ',payload)
    argument_check(argc<2**31 and reserved==0 and size==len(payload), 'invalid argument header')
    pointer=width//8
    end=24+(argc+envc+2)*pointer
    argument_check(end<=size<2**width, 'argument vector extent exceeds payload')
    offsets=[int.from_bytes(payload[i:i+pointer],'little') for i in range(24,end,pointer)]
    argument_check(offsets[argc]==0 and offsets[-1]==0, 'argument vectors require null sentinels')
    for offset in offsets[:argc]+offsets[argc+1:-1]:
        argument_check(end<=offset<size and payload.find(b'\0',offset)>=0, 'invalid argument string offset/terminator')

def argument_replies(build,manifest):
    width=build['layout']['ptr_width']
    argument_check(width in (32,64), 'unsupported target pointer width')
    protocol=build.get('entry_initialisation',{}).get('arguments')
    argument_check(protocol in (None,'bennett-argv-bytes-1'), 'unsupported process argument protocol: '+str(protocol))
    byte_service=protocol=='bennett-argv-bytes-1'
    argv,envp=argument_context(manifest)
    if 'argv_replies' in manifest:
        artifact=manifest['argv_replies'];path=pathlib.Path(artifact['path'])
        argument_check(sha(path)==artifact['sha256'], 'argv replies SHA256 changed during build')
        replies=load(path)
    elif byte_service:
        payload=argument_payload(width,argv,envp).hex()
        replies=[dict(service='bennett.argv.bytes',payload='00'*size,reply=payload) for size in (24,len(payload)//2)]
    else:
        header=len(argv).to_bytes(4,'little')+bytes(2*(width//8))
        replies=[dict(service='bennett.argv',payload='00'*len(header),reply=header.hex())]
    validate_argument_replies(replies,width,byte_service)
    return replies

def validate_argument_replies(replies,width,byte_service):
    argument_check(isinstance(replies,list), 'argv replies must be an array')
    if byte_service:
        argument_check(len(replies)==2, 'byte import requires two replies')
        payload=argument_hex(replies[0]['reply'])
        validate_argument_payload(payload,width)
        for row,size in zip(replies,(24,len(payload))):
            argument_check(row['service']=='bennett.argv.bytes' and row['payload']=='00'*size,
                           'byte import request service/capacity mismatch')
            argument_check(argument_hex(row['reply'])==payload, 'byte import replies must repeat the exact payload')
    else:
        size=4+2*(width//8)
        argument_check(len(replies)==1 and replies[0]['service']=='bennett.argv', 'expected one bennett.argv reply')
        argument_check(replies[0]['payload']=='00'*size, 'argv request payload must match zeroed header')
        argument_check(len(argument_hex(replies[0]['reply']))==size, 'argv reply header width mismatch')

def finalise(out):
    manifest = load(out/'manifest.json')
    launches = load(out/'launches.json')
    assert isinstance(launches, list), 'launch inventory must be an array'
    records = {}
    for launch in launches:
        entry = launch['entry']
        assert pathlib.Path(entry).name == entry and entry not in ('.','..'), 'invalid plugin entry path'
        d = out/entry
        for name in ('launch.bennett','build.json','certificate.json','coverage.json','blockers.json','launch-record.json'):
            assert (d/name).is_file(), f'missing §19.9 output {entry}/{name}'
        records[entry] = load(d/'build.json')
    replies_by_entry={}
    if any(a.lstrip('-')=='bennett-tier=reversible' for a in manifest['options']):
        replies_by_entry={entry:argument_replies(build,manifest) for entry,build in records.items()}
    record = dict(manifest, plugin_builds=records, build_flags=manifest['options'],
                  runtimes_sha256=manifest['runtimes']['sha256'], arith_sha256=manifest['arith']['sha256'],
                  snapshot_sha256=manifest['snapshot']['sha256'] if 'snapshot' in manifest else None, asm_table_sha256=None,
                  budget_tables={k: v.get('budget_table', v.get('budgets')) for k,v in records.items()},
                  layouts={k: v['layout'] for k,v in records.items()})
    raw = canonical(record)
    # The build hash excludes the newline, as in the plugin's own JCS build record.
    digest = hashlib.sha256(raw).hexdigest()
    (out/'build.json').write_bytes(raw + b'\n')
    (out/'build.sha256').write_text(digest+'\n')
    for launch in launches:
        d = out/launch['entry']
        cert = load(d/'certificate.json')
        cert['producer']['version'] = manifest['driver_version'] + '+build.' + digest
        cert['producer']['materialisation']['pipeline'] = manifest['pipeline'] + ',bennett'
        save(d/'certificate.json', cert)
        receipt = load(d/'launch-record.json')
        rel = launch['entry']+'/certificate.json'
        receipt['artifacts'][rel] = {'bytes': (d/'certificate.json').stat().st_size, 'sha256': sha(d/'certificate.json')}
        if launch['entry'] in replies_by_entry:
            replies=replies_by_entry[launch['entry']]
            save(d/'argv-replies.json',replies)
            receipt['artifacts'][launch['entry']+'/argv-replies.json']={'bytes':(d/'argv-replies.json').stat().st_size,'sha256':sha(d/'argv-replies.json')}
        receipt['driver_build_sha256'] = digest
        save(d/'launch-record.json', receipt)

if __name__=='__main__':
    finalise(pathlib.Path(sys.argv[1]))
