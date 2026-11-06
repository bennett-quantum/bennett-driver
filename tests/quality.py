"""Mutations exercise each independent quality ratchet input."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.argv = sys.argv[:1]


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
        import importlib.util
        spec = importlib.util.spec_from_file_location('driver_quality', ROOT/'scripts/quality.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for suffix, source in [('.rs', 'fn work() { if a && b { while ready() { step(); } } }'),
                               ('.cpp', 'int work() { if (a && b) { while (ready()) { step(); } } }'),
                               ('.py', 'def work():\n    if a and b:\n        while ready():\n            step()\n')]:
            lengths, complexity, wrappers = module.functions(source, suffix)
            self.assertEqual(len(lengths), 1)
            self.assertEqual(complexity, 4)
            self.assertEqual(wrappers, 0)

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
