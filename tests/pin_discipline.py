"""Exercise pin resolution and relocated driver configuration without live siblings."""
import os
import json
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
        sysroot = self.workspace / 'sysroot'
        (sysroot / 'include').mkdir(parents=True)
        production = ['--bennett-dialect=0.2.10', str(dummy)]
        native = ['--bennett-materialised=' + str(dummy)]
        keys = ('runtimes', 'arith', 'plugin', 'native-check', 'native-support', 'sysroot')
        for mode, required in ((production, keys[:3]), (native, ('runtimes', 'arith', 'native-check', 'native-support', 'sysroot')),
                               (native + ['--bennett-comparison-entry=top'], keys)):
            for missing in required:
                with self.subTest(mode=mode, missing=missing):
                    configured = ['--bennett-' + key + '=' + str(sysroot if key == 'sysroot' else dummy)
                                  for key in required if key != missing]
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

    def configured_environment(self, major):
        from toolchain import configure
        paths = configure(major)
        env = self.env | {'BENNETT_DRIVER_' + key.upper().replace('-', '_'): str(path)
                          for key, path in paths.items()}
        return paths, env

    def build_commands(self, args, env, out):
        result = subprocess.run([EXE, '--bennett-out=' + str(out), *args],
                                cwd=self.workspace, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        return [(c['stage'], c['argv']) for c in json.loads((out / 'manifest.json').read_text())['commands']]

    def test_sysroot_environment_and_flag_compile_the_same_program(self):
        root = self.workspace / 'sysroot'
        (root / 'include').mkdir(parents=True)
        (root / 'include/limits.h').write_text('#define INT_MAX 17\n')
        (root / 'include/sysroot_only.h').write_text('#define SYSROOT_VALUE 29\n')
        source = self.workspace / 'probe.c'
        for major in (18, 23):
            _, env = self.configured_environment(major)
            env['BENNETT_DRIVER_SYSROOT'] = str(root)
            args = ['--bennett-dialect=0.2.10', '--bennett-llvm-major=' + str(major), str(source)]
            for header, expression in (('limits.h', 'INT_MAX == 17'),
                                       ('sysroot_only.h', 'SYSROOT_VALUE == 29')):
                with self.subTest(major=major, header=header):
                    out = self.workspace / f'out-{major}-{header}'
                    source.write_text('#include <' + header + '>\nint probe(void) { return ' + expression + ' ? 0 : 3; }\n')
                    commands = []
                    for spelling in ('environment', 'flag'):
                        flags = [] if spelling == 'environment' else ['--bennett-sysroot=' + str(root)]
                        # An explicit flag takes precedence even over an unusable environment setting.
                        current_env = env if spelling == 'environment' else env | {'BENNETT_DRIVER_SYSROOT': str(root / 'absent')}
                        commands.append(self.build_commands([*args, *flags], current_env, out))
                        observed = subprocess.run([f'/usr/lib/llvm-{major}/bin/lli', '--entry-function=probe', out / 'host.bc'],
                                                  capture_output=True, timeout=10)
                        self.assertEqual(observed.returncode, 0, observed.stderr)
                        shutil.rmtree(out)
                    self.assertEqual(commands[0], commands[1])

    def test_unusable_sysroots_never_fall_back_to_host_headers(self):
        _, env = self.configured_environment(23)
        source = self.workspace / 'probe.c'
        source.write_text('#include <limits.h>\nint probe(void) { return INT_MAX > 0; }\n')
        file = self.workspace / 'file'
        file.write_text('not a directory')
        root = self.workspace / 'no-include'
        root.mkdir()
        invalid_include = self.workspace / 'invalid-include'
        invalid_include.mkdir()
        (invalid_include / 'include').write_text('not a directory')
        for path in (self.workspace / 'absent', file, root, invalid_include):
            for spelling in ('environment', 'flag'):
                with self.subTest(path=path, spelling=spelling):
                    flags = [] if spelling == 'environment' else ['--bennett-sysroot=' + str(path)]
                    out = self.workspace / ('out-' + path.name + '-' + spelling)
                    result = subprocess.run([EXE, '--bennett-dialect=0.2.10', '--bennett-out=' + str(out), str(source), *flags],
                                            env=env | {'BENNETT_DRIVER_SYSROOT': str(path)}, capture_output=True, text=True, timeout=30)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('BD-E-CONFIG', result.stderr)
                    self.assertIn(str(path), result.stderr)
                    self.assertIn('sysroot', result.stderr.lower())

    def test_external_environment_and_flags_produce_identical_commands(self):
        from toolchain import target_headers
        for major in (18, 23):
            paths, env = self.configured_environment(major)
            source = self.workspace / 'program.ll'
            source.write_text(target_headers(major) + 'define i32 @probe() { ret i32 0 }\n')
            args = ['--bennett-llvm-major=' + str(major), '--bennett-dialect=0.2.10', str(source)]
            # These three paths are all consumed by ordinary production.
            modes = [(args, ('plugin', 'runtimes', 'arith', 'sysroot'))]
            materialised = self.workspace / 'materialised.ll'
            materialised.write_text(target_headers(major) + 'define i32 @helper() { ret i32 0 }\n')
            harness = self.workspace / 'harness.c'
            harness.write_text('#include <limits.h>\nint main(void) { return INT_MAX == 2147483647 ? 0 : 3; }\n')
            classifier = self.workspace / 'original.c'
            classifier.write_text('int original(void) { return 0; }\n')
            layout = self.workspace / 'layout.json'
            layout.write_text(json.dumps(dict(null_size=4096, ptr_width=64, heap_base=69632,
                                             heap_limit_max=1048576, globals={}, interface_regions={})))
            # Comparison additionally consumes the check adapter, support and sysroot.
            modes.append((['--bennett-llvm-major=' + str(major), '--bennett-materialised=' + str(materialised),
                           '--bennett-comparison-layout=' + str(layout), '--bennett-layout-data-base=65536',
                           '--bennett-native-input=' + str(harness), '--bennett-classifier-input=' + str(classifier)],
                          ('runtimes', 'arith', 'native-check', 'native-support', 'sysroot')))
            for args, keys in modes:
                with self.subTest(major=major, keys=keys):
                    out = self.workspace / f'out-{major}-{len(keys)}'
                    commands = []
                    for spelling in ('environment', 'flag'):
                        flags = [] if spelling == 'environment' else ['--bennett-' + key + '=' + str(paths[key]) for key in keys]
                        commands.append(self.build_commands([*args, *flags], env if spelling == 'environment' else self.env, out))
                        if 'native-check' in keys:
                            for stage in ('native-support', 'classifier-frontend', 'native-O0', 'native-O2'):
                                self.assertIn(stage, [name for name, _ in commands[-1]])
                            for level in ('O0', 'O2'):
                                observed = subprocess.run([out / ('native-' + level)], capture_output=True, timeout=10)
                                self.assertEqual(observed.returncode, 0, observed.stderr)
                        shutil.rmtree(out)
                    self.assertEqual(commands[0], commands[1])

    def test_empty_external_environment_paths_are_loud(self):
        for key in ('PLUGIN', 'RUNTIMES', 'ARITH', 'ARITH_GENERATOR', 'NATIVE_CHECK', 'NATIVE_SUPPORT', 'SYSROOT'):
            with self.subTest(key=key):
                variable = 'BENNETT_DRIVER_' + key
                result = subprocess.run([EXE, '--bennett-dialect=0.2.10',
                                         '--bennett-out=' + str(self.workspace / key), 'unused.bc'],
                                        env=self.env | {variable: ''}, capture_output=True, text=True, timeout=15)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('BD-E-CONFIG', result.stderr)
                self.assertIn(variable, result.stderr)

    def test_environment_plugin_path_is_protected_from_output_aliasing(self):
        _, env = self.configured_environment(23)
        plugin = self.workspace / 'plugin.so'
        plugin.write_bytes(b'protected plugin input')
        source = self.workspace / 'materialised.ll'
        source.write_text('define i32 @main() { ret i32 0 }\n')
        result = subprocess.run([EXE, '--bennett-materialised=' + str(source),
                                 '--bennett-out=' + str(self.workspace / 'out'), '--bennett-comparison-output=' + str(plugin)],
                                env=env | {'BENNETT_DRIVER_PLUGIN': str(plugin)}, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('BD-E-OUTPUT-PATH', result.stderr)
        self.assertEqual(plugin.read_bytes(), b'protected plugin input')


unittest.main()
