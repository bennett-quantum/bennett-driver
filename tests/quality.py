"""Mutations exercise each independent quality ratchet input."""
import importlib.util
import itertools
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.argv = sys.argv[:1]
SPEC = importlib.util.spec_from_file_location('driver_quality', ROOT/'scripts/quality.py')
quality = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(quality)
IDENTIFIER = 'bennett-'+'driver-abc'
# Only actual code attributes are exempt; all literal/comment contents count.
PLACEMENTS = (('literal', [IDENTIFIER]), ('attribute', []))
LITERALS = (('"', '"'), ('b"', '"'), ('c"', '"')) + tuple(
    (prefix+'#'*hashes+'"', '"'+'#'*hashes)
    for prefix, hashes in itertools.product(('r', 'br', 'cr'), (0, 1, 2, 3, 16, 255, 256)))
POSITIONS = ('{}', '    {}', '/* prefix */ {} /* suffix */')
LINES = ('{}\n{}\n{}', '{}{}\n{}', '{}\n{}{}', '{}{}{}')
CONTEXTS = ('{}', '// " r###" /*\n{}', '/* outer /* " */ r###" */\n{}',
            'let mark = \'#\'; let byte = b\'\\\'\'; {}',
            'let quote = \'"\'; let unicode = \'\\u{{22}}\'; {}',
            'fn borrow<\'a>(_: &\'a str) {{}} {}',
            r'let escaped = "escaped \\ and \" quote"; {}',
            'let prior = r###" "## /* // "###; {}')
ATTRIBUTE = '#[ignore = "'+IDENTIFIER+'"]'
LEXICAL_CONTROLS = (
    ('// '+ATTRIBUTE, [IDENTIFIER]),
    ('/*\n'+ATTRIBUTE+'\n*/', [IDENTIFIER]),
    ('/* outer /* inner */\n'+ATTRIBUTE+'\n*/\n'+ATTRIBUTE, [IDENTIFIER]),
    ('/* outer /*\n'+ATTRIBUTE+'\n*/ still outer */\n'+ATTRIBUTE, [IDENTIFIER]),
    (ATTRIBUTE+' '+ATTRIBUTE+'\nfn promised() {}', []),
    (r'#[ignore = "escaped \" '+IDENTIFIER+'"]\nfn promised() {}', []),
    ('#[ignore = "ordinary"] // '+IDENTIFIER, [IDENTIFIER]))


def lexical_case(opener, closer, position, line, placement, context):
    attribute = '#[ignore = "'+IDENTIFIER+'"]'
    # A zero-hash raw literal cannot contain double quotes: use non-attribute text.
    payload = {'literal': attribute, 'attribute': 'ordinary output'}[placement]
    payload = {'"': payload.replace('"', '\\"')}.get(closer, payload)
    payload = {('r"', 'literal'): IDENTIFIER, ('br"', 'literal'): IDENTIFIER,
               ('cr"', 'literal'): IDENTIFIER}.get((opener, placement), payload)
    literal = line.format(opener, position.format(payload), closer)
    tail = {'literal': '', 'attribute': '\n'+position.format(attribute)+'\nfn promised() {}'}[placement]
    return context.format('let text = '+literal+';'+tail)


def emitted_source(message):
    return 'fn main() {\n    print!("{}", r###"\n#[ignore = "'+message+'"]\n"###);\n}\n'


class QualityRatchet(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for directory in ('src', 'scripts', 'docs'):
            (self.root/directory).mkdir()
        shutil.copyfile(ROOT/'scripts/quality.py', self.root/'scripts/quality.py')
        self.source = self.root/'src/work.rs'
        self.source.write_text('fn work() { perform(); }\n')
        (self.root/'docs/quality.md').write_text('# Quality\n')
        subprocess.run(['git', 'init', '-q', self.root], check=True, capture_output=True)
        subprocess.run(['git', '-C', self.root, 'add', '--', 'src', 'scripts', 'docs'], check=True)
        self.assertEqual(self.run_check('--record').returncode, 0)

    def run_check(self, *args):
        return subprocess.run(['python3', self.root/'scripts/quality.py', *args],
                              capture_output=True, text=True, timeout=15)

    def test_language_metrics_have_hand_derived_control_depth(self):
        cases = [('.rs', 'fn work() { if a && b { while ready() { step(); } } }'),
                 ('.cpp', 'int work() { if (a && b) { while (ready()) { step(); } } }'),
                 ('.py', 'def work():\n    if a and b:\n        while ready():\n            step()\n')]
        results = [quality.functions(source, suffix) for suffix, source in cases]
        self.assertEqual([len(lengths) for lengths, _, _ in results], [1, 1, 1])
        self.assertEqual([mass for _, mass, _ in results], [4, 4, 4])
        self.assertEqual([wrappers for _, _, wrappers in results], [0, 0, 0])

    def test_generated_literal_and_attribute_contexts(self):
        dimensions = itertools.product(LITERALS, POSITIONS, LINES, PLACEMENTS, CONTEXTS)
        cases = ((lexical_case(opener, closer, position, line, placement, context), expected)
                 for (opener, closer), position, line, (placement, expected), context in dimensions)
        for source, expected in itertools.chain(cases, LEXICAL_CONTROLS):
            with self.subTest(source=source):
                actual = quality.source_identifiers('src/work.rs', source)
                self.assertEqual([entry.rsplit(':', 1)[1] for entry in actual], expected)

    def test_multiline_attribute_preserves_following_line_numbers(self):
        source = '#[ignore = "promised:\n'+IDENTIFIER+'"]\nfn work() { print!("'+IDENTIFIER+'"); }'
        self.assertEqual(quality.source_identifiers('src/work.rs', source), ['src/work.rs:3:'+IDENTIFIER])

    def test_unclosed_rust_tokens_fail_loudly(self):
        with self.assertRaisesRegex(ValueError, 'unclosed Rust block comment'):
            list(quality.rust_tokens('/* outer /* inner */'))
        with self.assertRaisesRegex(ValueError, 'unclosed Rust raw string'):
            list(quality.rust_tokens('r###"ordinary output"##'))
        with self.assertRaisesRegex(ValueError, 'unclosed Rust string'):
            list(quality.rust_tokens('"ordinary output'))

    def test_emitted_raw_string_identifier_reproduction(self):
        self.source.write_text(emitted_source('ordinary output'))
        self.assertEqual(self.run_check('--record').returncode, 0)
        self.source.write_text(emitted_source(IDENTIFIER))
        binary = self.root/'work'
        subprocess.run(['rustc', '--edition=2024', self.source, '-o', binary],
                       check=True, capture_output=True, timeout=10)
        output = subprocess.check_output([binary], text=True, timeout=3)
        self.assertEqual(output, '\n#[ignore = "'+IDENTIFIER+'"]\n')
        result = self.run_check()
        self.assertEqual(result.returncode, 1, result.stdout+result.stderr)
        self.assertIn('process_identifiers', result.stderr)
        self.assertIn('src/work.rs:3:'+IDENTIFIER, result.stderr)

    def test_unchanged_and_improved_sources_pass(self):
        self.assertEqual(self.run_check().returncode, 0)
        self.source.write_text('fn work() { let value = 7; consume(value); }\n')
        self.assertEqual(self.run_check().returncode, 0)

    def test_branch_growth_fails(self):
        self.source.write_text('fn work() { if ready() { perform(); } }\n')
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('complexity', result.stderr)

    def test_longer_function_distribution_fails(self):
        self.source.write_text('fn work() {\n'+'    consume();\n'*40+'}\n')
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('length', result.stderr)

    def test_extra_trivial_wrapper_fails(self):
        self.source.write_text(self.source.read_text()+'fn other() { forward(); }\n')
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('wrappers', result.stderr)

    def test_tracked_litter_fails(self):
        (self.root/'debug.log').write_text('scratch\n')
        subprocess.run(['git', '-C', self.root, 'add', '--', 'debug.log'], check=True)
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('litter', result.stderr)

    def test_process_identifier_in_product_fails(self):
        self.source.write_text('// '+ 'bennett-'+'driver-abc'+'\n'+self.source.read_text())
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('process_identifiers', result.stderr)

    def test_inline_production_body_identifiers_are_checked(self):
        self.source.write_text('fn work() { println!("ordinary output"); }\n')
        self.assertEqual(self.run_check('--record').returncode, 0)
        self.source.write_text('fn work() { println!("'+'bennett-'+'driver-abc'+'"); }\n')
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('process_identifiers', result.stderr)

    def test_named_promised_switch_stays_exempt(self):
        self.source.write_text('#[test]\n#[ignore = "promised: '+'bennett-'+'driver-abc'+'"]\n'
                               'fn promised_capability() { perform(); }\n')
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_named_switch_does_not_hide_inline_body(self):
        self.source.write_text('#[test]\n#[ignore = "promised: '+'bennett-'+'driver-abc'+'"] '
                               'fn promised_capability() { println!("'+'bennett-'+'driver-def'+'"); }\n')
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('process_identifiers', result.stderr)
        self.assertIn('bennett-'+'driver-def', result.stderr)

    def test_python_test_name_does_not_hide_inline_body(self):
        path = self.root/'src/work.py'
        path.write_text('def test_work(): print("ordinary output")\n')
        subprocess.run(['git', '-C', self.root, 'add', '--', 'src/work.py'], check=True)
        self.assertEqual(self.run_check('--record').returncode, 0)
        path.write_text('def test_work(): print("'+'bennett-'+'driver-abc'+'")\n')
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('process_identifiers', result.stderr)

    def test_extensionless_script_identifiers_are_checked(self):
        path = self.root/'scripts/tool'
        path.write_text('# '+ 'bennett-'+'driver-abc'+'\n')
        subprocess.run(['git', '-C', self.root, 'add', '--', 'scripts/tool'], check=True)
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('process_identifiers', result.stderr)

    def test_new_file_cannot_hide_existing_complexity(self):
        path = self.root/'src/hidden.rs'
        path.write_text('fn hidden() { if ready() { perform(); } }\n')
        subprocess.run(['git', '-C', self.root, 'add', '--', 'src/hidden.rs'], check=True)
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('complexity', result.stderr)


unittest.main()
