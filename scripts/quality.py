#!/usr/bin/env python3
"""Ratchet tracked-source structure and hygiene against docs/quality.md."""
import argparse
import ast
import fnmatch
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASELINE = re.compile(r'<!-- quality-baseline -->\s*```json\n(.*?)\n```', re.S)
LIMITS = (25, 50, 100, 200, 300)
MAX_WRAPPER_LINES = 6  # Conservative short single-expression forwarding heuristic.
# Track only process identifier shapes; language/contract/version names are not IDs.
PROCESS = re.compile(r'\b(?:bennett-driver|brt|bp)-[a-z0-9]{3}(?:\.[0-9]+)?\b|'
                     r'\bbennett-(?=[a-z0-9]{3}\b)(?=[a-z0-9]*[0-9])[a-z0-9]{3}\b|'
                     r'\bjob/[a-z0-9-]+|\bshift[ -][0-9]+', re.I)
LITTER = ('*.pyc', '*.log', '*.darc', '*LAST-RUN*', '*PROGRESS*', '*/LOCK', '*.lock')
STRINGS = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])\'', re.S)
CONTROL = re.compile(r'\b(?:if|else|for|while|match|catch)\b|&&|\|\||[{}?]')
RUST_FN = re.compile(r'\bfn\s+([A-Za-z_][A-Za-z_0-9]*)\b[^;{}]*\{')
CPP_FN = re.compile(r'\b([A-Za-z_][A-Za-z_0-9]*)\s*\([^;{}]*\)\s*(?:const\s*)?\{')


def python_mass(node, depth=0):
    control = isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While,
                               ast.Try, ast.ExceptHandler, ast.IfExp, ast.Match))
    own = 1 + depth if control else 0
    if isinstance(node, ast.BoolOp):
        own += len(node.values) - 1
    return own + sum(python_mass(child, depth + control) for child in ast.iter_child_nodes(node))


def brace_mass(code):
    stack = []
    pending = False
    mass = 0
    for token in CONTROL.findall(code):
        if token == '{':
            stack.append(pending)
            pending = False
        elif token == '}':
            if not stack:
                raise ValueError('unbalanced source braces')
            stack.pop()
        elif token in ('&&', '||', '?'):
            mass += 1
        else:
            mass += 1 + sum(stack)
            pending = True
    return mass


def functions(code, suffix):
    if suffix == '.py':
        tree = ast.parse(code)
        nodes = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        lengths = [node.end_lineno - node.lineno + 1 for node in nodes]
        wrappers = sum(len(node.body) == 1 and isinstance(node.body[0], (ast.Return, ast.Expr))
                       and isinstance(node.body[0].value, ast.Call) for node in nodes)
        return lengths, python_mass(tree), wrappers
    # Replace comments and literals with whitespace while preserving line numbers.
    clean = STRINGS.sub(lambda m: re.sub(r'[^\n]', ' ', m[0]), code)
    lengths, wrappers = [], 0
    pattern = RUST_FN if suffix == '.rs' else CPP_FN
    for match in pattern.finditer(clean):
        if match[1] in ('if', 'for', 'while', 'switch', 'catch'):
            continue
        start = match.end() - 1
        depth, end = 1, start + 1
        while end < len(clean) and depth:
            depth += (clean[end] == '{') - (clean[end] == '}')
            end += 1
        if depth:
            raise ValueError(f'unclosed function {match[1]}')
        length = clean.count('\n', match.start(), end) + 1
        lengths.append(length)
        body = clean[start + 1:end - 1].strip()
        wrappers += bool(length <= MAX_WRAPPER_LINES and '(' in body and not re.search(r'\b(?:let|if|for|while|match)\b|[={} ]=', body)
                         and body.count(';') <= 1)
    return lengths, brace_mass(clean), wrappers


def measure():
    tracked = subprocess.check_output(['git', '-C', ROOT, 'ls-files', '-z']).decode().split('\0')
    metrics = {'files': {}, 'litter': [], 'process_identifiers': []}
    for name in sorted(set(tracked) - {''}):
        path = ROOT/name
        if not path.is_file():
            continue
        if name != 'Cargo.lock' and ('__pycache__' in path.parts or any(fnmatch.fnmatch(name, glob) for glob in LITTER)):
            metrics['litter'].append(name)
        if path.parts[len(ROOT.parts)] not in ('src', 'scripts', 'tests'):
            continue
        source = path.read_bytes().decode('utf-8', errors='replace')
        for number, line in enumerate(source.splitlines(), 1):
            # Test names and named promised switches are explicitly allowed.
            if re.match(r'\s*(?:fn |def test_|#\[ignore)', line):
                continue
            for match in PROCESS.finditer(line):
                metrics['process_identifiers'].append(f'{name}:{number}:{match[0]}')
        if path.suffix in ('.rs', '.cpp', '.c', '.h', '.py'):
            lengths, complexity, wrappers = functions(source, path.suffix)
            metrics['files'][name] = {'functions': len(lengths), 'max_length': max(lengths, default=0),
                                    'length_tails': [sum(length > limit for length in lengths) for limit in LIMITS],
                                    'complexity': complexity, 'wrappers': wrappers}
    return metrics


def regressions(actual, baseline):
    failures = []
    for name, metrics in actual['files'].items():
        previous = baseline['files'].get(name, dict(max_length=0, length_tails=[0]*len(LIMITS), complexity=0, wrappers=0))
        for metric in ('max_length', 'complexity', 'wrappers'):
            if metrics[metric] > previous[metric]:
                failures.append(f'{name}: {metric} {metrics[metric]} > {previous[metric]}')
        for limit, count, before in zip(LIMITS, metrics['length_tails'], previous['length_tails']):
            if count > before:
                failures.append(f'{name}: length >{limit}: {count} > {before}')
    for metric in ('litter', 'process_identifiers'):
        added = sorted(set(actual[metric]) - set(baseline[metric]))
        if added:
            failures.append(f'{metric}: {added}')
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', action='store_true', help='record a reviewed baseline in docs/quality.md')
    parser.add_argument('--show', action='store_true', help='print measured metrics')
    args = parser.parse_args()
    actual = measure()
    path = ROOT/'docs/quality.md'
    document = path.read_text()
    if args.show:
        print(json.dumps(actual, sort_keys=True, indent=2))
        return 0
    if args.record:
        if actual['litter'] or actual['process_identifiers']:
            raise ValueError('remove litter and process_identifiers before recording the baseline')
        block = '<!-- quality-baseline -->\n```json\n' + json.dumps(actual, sort_keys=True, indent=2) + '\n```'
        path.write_text(BASELINE.sub(lambda _: block, document) if BASELINE.search(document) else document+'\n'+block+'\n')
        return 0
    match = BASELINE.search(document)
    if not match:
        raise ValueError('missing quality baseline in docs/quality.md; record and review one explicitly')
    failures = regressions(actual, json.loads(match[1]))
    if failures:
        print('Quality regression:\n'+'\n'.join(failures), file=sys.stderr)
        return 1
    print('Quality baseline: function lengths, cognitive mass, wrappers and hygiene did not worsen')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, SyntaxError, subprocess.CalledProcessError) as error:
        raise SystemExit(f'quality: {error}')
