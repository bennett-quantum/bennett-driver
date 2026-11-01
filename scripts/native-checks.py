"""Comparison-only checks on canonical, verified LLVM IR, before codegen.

The producer's device module stays byte-identical. Checks precede optimisation:
constant invalid divisions otherwise disappear as poison even on trapping CPUs.
"""
import json, pathlib, re, sys

sys.set_int_max_str_digits(0)
source, destination, receipt = map(pathlib.Path, sys.argv[1:])
text = source.read_text()
prefix = '__bennett_rt_native_checked_'
if '@'+prefix in text:
    raise ValueError('BD-E-NATIVE-CHECKS: comparison helper name collision')

def operands(text):
    """Split LLVM operands/attachments without splitting constant expressions."""
    depth = 0
    quoted = escaped = False
    start = 0
    parts = []
    for i, char in enumerate(text):
        if escaped:
            escaped = False
        elif char == '\\' and quoted:
            escaped = True
        elif char == '"':
            quoted = not quoted
        elif not quoted:
            if char in '([{<': depth += 1
            elif char in ')]}>': depth -= 1
            elif char == ',' and depth == 0:
                parts.append(text[start:i].strip())
                start = i+1
    parts.append(text[start:].strip())
    return parts

helpers = set()
lines = []
count = 0
for line in text.splitlines():
    match = re.match(r'^(\s*%(?:[-a-zA-Z$._0-9]+|"(?:\\.|[^"\\])*")\s*=\s*)([su](?:div|rem))(?: exact)? i([0-9]+) (.*)$', line)
    if match:
        result, op, width, rest = match.groups()
        parts = operands(rest)
        if len(parts) < 2:
            raise ValueError('BD-E-NATIVE-CHECKS: malformed division: '+line)
        helpers.add((op, int(width)))
        tail = ', '+', '.join(parts[2:]) if len(parts)>2 else ''
        lines.append(f'{result}call i{width} @{prefix}{op}_i{width}(i{width} {parts[0]}, i{width} {parts[1]}){tail}')
        count += 1
    elif re.match(r'^\s*unreachable(?:\s*,.*)?$', line):
        lines.extend(['  call void @__bennett_nz_fault(i64 4)', line])
    elif re.match(r'^\s*(?:tail )?call void @llvm.trap\(\)', line):
        lines.append('  call void @__bennett_nz_fault(i64 4)')
    else:
        # Vectors must already be scalarised by materialisation. Do not silently
        # claim coverage if a new LLVM division spelling escaped the parser.
        if re.search(r'=\s*[su](?:div|rem)\b', line):
            raise ValueError('BD-E-NATIVE-CHECKS: division requires materialised scalar IR: '+line)
        lines.append(line)

if '@__bennett_nz_fault(' not in text:
    lines.append('declare void @__bennett_nz_fault(i64)')
for op, width in sorted(helpers):
    signed = op.startswith('s')
    lines.extend([f'define internal i{width} @{prefix}{op}_i{width}(i{width} %a, i{width} %b) {{',
        'entry:', f'  %zero = icmp eq i{width} %b, 0',
        '  br i1 %zero, label %divzero, label %nonzero', 'divzero:',
        '  call void @__bennett_nz_fault(i64 5)', '  unreachable', 'nonzero:'])
    if signed:
        lines.extend([f'  %minimum = icmp eq i{width} %a, {-2**(width-1)}',
            f'  %minusone = icmp eq i{width} %b, -1',
            '  %overflow = and i1 %minimum, %minusone',
            '  br i1 %overflow, label %bad, label %ok', 'bad:',
            '  call void @__bennett_nz_fault(i64 6)', '  unreachable', 'ok:'])
    lines.extend([f'  %result = {op} i{width} %a, %b', f'  ret i{width} %result', '}'])
destination.write_text('\n'.join(lines)+'\n')
receipt.write_text(json.dumps(dict(subject='materialised', status='incomplete',
    division_by_zero=True, signed_division_overflow=True, explicit_fault=True,
    invalid_free=True, double_free=True, general_memory=False, use_after_free=False,
    out_of_live_allocation=False, source_ub_erased_by_optimisation=False,
    checked_divisions=count, blocked_on=['brt-2qs'],
    required_change='Add materialised live-allocation load/store/range checks, including freed storage; source UBSan is separate'),
    sort_keys=True, separators=(',', ':'))+'\n')
