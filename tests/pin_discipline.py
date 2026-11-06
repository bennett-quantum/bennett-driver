"""Exercise pin resolution and relocated driver configuration without live siblings."""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXE = pathlib.Path(sys.argv.pop(1)).resolve()
PIN = '1' * 40
OTHER = '2' * 40


class PinDiscipline(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'], prefix='pin-discipline-')
        self.addCleanup(self.temp.cleanup)
        self.workspace = pathlib.Path(self.temp.name)
        self.root = self.workspace / 'driver'
        self.root.mkdir()
        shutil.copytree(ROOT / 'tests', self.root / 'tests', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(ROOT / 'scripts', self.root / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
        (self.root / 'gate.toml').write_text('[siblings."bennett-plugin"]\nsha = "' + PIN + '"\n')
        self.live = self.workspace / 'bennett-plugin'
        self.checkout(self.live, OTHER)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(('BENNETT_', 'GIT_'))}
        self.env['PYTHONDONTWRITEBYTECODE'] = '1'

    def checkout(self, directory, sha):
        (directory / '.git').mkdir(parents=True)
        (directory / '.git/HEAD').write_text(sha + '\n')

    def resolve(self):
        code = "import sys; sys.path.insert(0, 'scripts'); from pinned_siblings import sibling; print(sibling('bennett-plugin'))"
        return subprocess.run(['python3', '-c', code], cwd=self.root, env=self.env,
                              capture_output=True, text=True, timeout=15)

    def test_cache_wins_over_live_checkout_and_legacy_override(self):
        cache = self.root / '.tmp/gate/cache' / ('bennett-plugin@' + PIN[:12]) / 'bennett-plugin'
        self.checkout(cache, PIN)
        self.env['BENNETT_DRIVER_MODERN_PLUGIN_ROOT'] = str(self.live)
        result = self.resolve()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(cache))

    def test_gate_layout_wins_over_cache(self):
        cache = self.root / '.tmp/gate/cache' / ('bennett-plugin@' + PIN[:12]) / 'bennett-plugin'
        self.checkout(cache, OTHER)
        layout = self.workspace / 'layout'
        self.checkout(layout / 'bennett-plugin', PIN)
        self.env['BENNETT_GATE_LAYOUT'] = str(layout)
        result = self.resolve()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(layout / 'bennett-plugin'))

    def test_missing_pin_has_one_actionable_message(self):
        result = self.resolve()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(result.stderr.splitlines()), 1, result.stderr)
        for expected in ('bennett-plugin', PIN, OTHER, 'gate_run.py verify --repo', '--sha HEAD'):
            self.assertIn(expected, result.stderr)

    def test_mismatched_layout_is_loud_even_with_valid_cache(self):
        cache = self.root / '.tmp/gate/cache' / ('bennett-plugin@' + PIN[:12]) / 'bennett-plugin'
        self.checkout(cache, PIN)
        self.env['BENNETT_GATE_LAYOUT'] = str(self.workspace)
        result = self.resolve()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(result.stderr.splitlines()), 1, result.stderr)
        for expected in ('bennett-plugin', PIN, OTHER, 'mismatch'):
            self.assertIn(expected, result.stderr)

    def test_cache_head_is_verified(self):
        cache = self.root / '.tmp/gate/cache' / ('bennett-plugin@' + PIN[:12]) / 'bennett-plugin'
        self.checkout(cache, OTHER)
        result = self.resolve()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(result.stderr.splitlines()), 1, result.stderr)
        for expected in (PIN, OTHER, 'mismatch'):
            self.assertIn(expected, result.stderr)

    def test_missing_gate_sibling_does_not_fall_back_to_cache(self):
        cache = self.root / '.tmp/gate/cache' / ('bennett-plugin@' + PIN[:12]) / 'bennett-plugin'
        self.checkout(cache, PIN)
        self.env['BENNETT_GATE_LAYOUT'] = str(self.workspace / 'absent-layout')
        result = self.resolve()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(result.stderr.splitlines()), 1, result.stderr)
        self.assertIn('absent-layout', result.stderr)

    def test_real_inputs_reader_passes_with_empty_live_siblings(self):
        shutil.copyfile(ROOT / 'gate.toml', self.root / 'gate.toml')
        (self.root / '.tmp/gate').mkdir(parents=True)
        (self.root / '.tmp/gate/cache').symlink_to(ROOT / '.tmp/gate/cache', target_is_directory=True)
        (self.root / '.tmp').mkdir(exist_ok=True)
        shutil.rmtree(self.live)
        self.live.mkdir()
        if os.environ.get('BENNETT_GATE_LAYOUT'):
            self.env['BENNETT_GATE_LAYOUT'] = os.environ['BENNETT_GATE_LAYOUT']
        result = subprocess.run(['python3', self.root / 'tests/inputs.py', EXE], env=self.env,
                                capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_relocated_driver_requires_every_external_path(self):
        dummy = self.workspace / 'dummy'
        dummy.write_text('define i32 @main() { ret i32 0 }\n')
        production = ['--bennett-dialect=0.2.10', str(dummy)]
        native = ['--bennett-materialised=' + str(dummy)]
        keys = ('runtimes', 'arith', 'plugin', 'native-check', 'native-support', 'sysroot')
        for mode, required in ((production, keys[:3]), (native, ('runtimes', 'arith', 'native-check', 'native-support', 'sysroot')),
                               (native + ['--bennett-comparison-entry=top'], keys)):
            for missing in required:
                with self.subTest(mode=mode, missing=missing):
                    configured = ['--bennett-' + key + '=' + str(dummy) for key in required if key != missing]
                    out = self.workspace / ('out-' + str(len(list(self.workspace.glob('out-*')))))
                    result = subprocess.run([EXE, '--bennett-out=' + str(out), *mode, *configured],
                                            cwd=self.workspace, env=self.env, capture_output=True, text=True, timeout=15)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('BD-E-CONFIG', result.stderr)
                    self.assertIn('--bennett-' + missing, result.stderr)

    def test_missing_or_empty_tmpdir_is_loud(self):
        for value in (None, ''):
            with self.subTest(value=value):
                env = self.env.copy()
                env.pop('TMPDIR', None)
                if value is not None:
                    env['TMPDIR'] = value
                result = subprocess.run([EXE, '--bennett-dialect=0.2.10', '--bennett-out=' + str(self.workspace / 'out'), 'missing.bc'],
                                        env=env, capture_output=True, text=True, timeout=15)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('BD-E-CONFIG', result.stderr)
                self.assertIn('TMPDIR', result.stderr)

    def test_arithmetic_generation_requires_an_explicit_generator(self):
        from toolchain import configure, target_headers
        paths = configure(23)
        env = self.env | {'BENNETT_DRIVER_' + key.upper().replace('-', '_'): str(path)
                          for key, path in paths.items() if key != 'arith-generator'}
        source = self.workspace / 'powi.ll'
        source.write_text(target_headers(23) + 'declare i32 @__bennett_sf_powi_f32_i7(i32, i7)\n'
                          'define i32 @main() { %x = call i32 @__bennett_sf_powi_f32_i7(i32 0, i7 1)\n ret i32 %x }\n')
        result = subprocess.run([EXE, '--bennett-materialised=' + str(source),
                                 '--bennett-out=' + str(self.workspace / 'out')],
                                env=env, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('BD-E-CONFIG', result.stderr)
        self.assertIn('--bennett-arith-generator', result.stderr)


unittest.main()
