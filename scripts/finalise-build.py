#!/usr/bin/env python3
"""Attach a canonical driver build record without changing ISA object bytes."""
import hashlib, json, pathlib, sys
out = pathlib.Path(sys.argv[1])
def load(p): return json.loads(p.read_text())
def canonical(value): return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p, value): p.write_bytes(canonical(value) + b'\n')
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
    if any(a.lstrip('-')=='bennett-tier=reversible' for a in manifest['options']):
        size=4+2*(records[launch['entry']]['layout']['ptr_width']//8)
        replies=load(pathlib.Path(manifest['argv_replies']['path'])) if 'argv_replies' in manifest else [dict(service='bennett.argv',payload='00'*size,reply='00'*size)]
        assert isinstance(replies,list) and len(replies)==1 and replies[0]['service']=='bennett.argv', 'expected one bennett.argv reply'
        assert replies[0]['payload']=='00'*size, 'argv request payload must match zeroed header'
        assert len(replies[0]['reply'])==2*size and len(bytes.fromhex(replies[0]['reply']))==size, 'argv reply header width mismatch'
        save(d/'argv-replies.json',replies)
        receipt['artifacts'][launch['entry']+'/argv-replies.json']={'bytes':(d/'argv-replies.json').stat().st_size,'sha256':sha(d/'argv-replies.json')}
    receipt['driver_build_sha256'] = digest
    save(d/'launch-record.json', receipt)
