"""Independent byte-layout oracles and malformed process transport controls."""
import copy
import importlib.util
import json
from pathlib import Path
import struct


def rejects(operation):
    try:
        operation()
    except ValueError as error:
        assert 'BD-E-PROCESS-ARGS' in str(error), error
    else:
        raise AssertionError('invalid process input was accepted')


def check_payloads(codec, width):
    base, total, format_ = {32: (48, 57, '<6I'), 64: (72, 81, '<6Q')}[width]
    expected = struct.pack('<IIQQ', 3, 0, 1, total)
    expected += struct.pack(format_, base, base + 2, base + 4, 0, base + 5, 0)
    expected += b'A\0A\0\0X=\xff\0'
    actual = codec.argument_payload(width, [b'A', b'A', b''], [b'X=\xff'])
    assert actual == expected
    codec.validate_argument_payload(actual, width)
    pointer = width // 8
    changes = [(4, (1).to_bytes(4, 'little')), (16, (total + 1).to_bytes(8, 'little')),
               (0, (2**31).to_bytes(4, 'little')), (8, (2**64 - 1).to_bytes(8, 'little')),
               (24 + 3 * pointer, (1).to_bytes(pointer, 'little')),
               (24, bytes(pointer)), (24, (2**width - 1).to_bytes(pointer, 'little')),
               (len(actual) - 1, b'!')]
    for offset, replacement in changes:
        changed = bytearray(actual)
        changed[offset:offset + len(replacement)] = replacement
        rejects(lambda: codec.validate_argument_payload(changed, width))
    rejects(lambda: codec.validate_argument_payload(actual[:23], width))
    return actual


def check_reply_pairs(codec, width, payload):
    build = dict(layout=dict(ptr_width=width), entry_initialisation=dict(arguments='bennett-argv-bytes-1'))
    expected_empty = struct.pack('<IIQQ', 0, 0, 0, 24 + width // 4) + bytes(width // 4)
    empty = codec.argument_replies(build, {})
    assert [bytes.fromhex(row['reply']) for row in empty] == [expected_empty] * 2
    assert [len(bytes.fromhex(row['payload'])) for row in empty] == [24, len(expected_empty)]
    valid = [dict(service='bennett.argv.bytes', payload='00' * size, reply=payload.hex())
             for size in (24, len(payload))]
    codec.validate_argument_replies(valid, width, True)
    variants = [valid[:1], valid + valid[:1]]
    for index, key, value in [(0, 'service', 'bennett.argv'), (0, 'payload', '00' * 25),
                              (1, 'payload', '00' * (len(payload) - 1)),
                              (1, 'reply', expected_empty.hex()), (0, 'reply', 'invalid')]:
        changed = copy.deepcopy(valid)
        changed[index][key] = value
        variants.append(changed)
    for changed in variants:
        rejects(lambda: codec.validate_argument_replies(changed, width, True))
    legacy = codec.argument_replies(dict(layout=dict(ptr_width=width)), {})
    assert legacy == [dict(service='bennett.argv', payload='00' * (4 + width // 4),
                           reply='00' * (4 + width // 4))]


def check_context(codec, directory):
    path = directory / 'codec-context.json'
    valid = dict(schema='bennett-driver-process-arguments-1',
                 argv=['program', dict(hex='ff'), ''], envp=['X=abc', dict(hex='583dff')])
    path.write_text(json.dumps(valid))
    manifest = dict(process_arguments=dict(path=str(path), sha256=codec.sha(path)))
    assert codec.argument_context(manifest) == ([b'program', b'\xff', b''], [b'X=abc', b'X=\xff'])
    path.write_text(json.dumps(valid | dict(argv=['changed'])))
    rejects(lambda: codec.argument_context(manifest))
    for change in [dict(schema='other'), dict(argv=True), dict(envp='X=abc'),
                   dict(argv=['a\0b']), dict(argv=[dict(hex='00')]), dict(envp=[dict(hex='gg')])]:
        path.write_text(json.dumps(valid | change))
        manifest['process_arguments']['sha256'] = codec.sha(path)
        rejects(lambda: codec.argument_context(manifest))
    for value in ['f f', 'bad', 3]:
        rejects(lambda: codec.argument_hex(value))


def check_codec(directory):
    script = Path(__file__).resolve().parents[1] / 'scripts/finalise-build.py'
    spec = importlib.util.spec_from_file_location('driver_process_arguments', script)
    codec = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(codec)
    for width in (32, 64):
        payload = check_payloads(codec, width)
        check_reply_pairs(codec, width, payload)
    check_context(codec, directory)
    rejects(lambda: codec.argument_replies(dict(layout=dict(ptr_width=16)), {}))
    rejects(lambda: codec.argument_replies(dict(layout=dict(ptr_width=64),
        entry_initialisation=dict(arguments='bennett-argv-bytes-2')), {}))
    print('32/64-bit process payloads: exact byte oracles, empty vectors, duplicates/non-UTF8, malformed transport rejection')
