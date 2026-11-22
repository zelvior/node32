import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class AndroidConfigureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='node-android-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for filename in ('android-configure', 'android_configure.py'):
            shutil.copy(ROOT / filename, self.root / filename)
        self.ndk = self.root / 'android-ndk'
        self.bin = self.ndk / 'toolchains/llvm/prebuilt/linux-x86_64/bin'
        self.bin.mkdir(parents=True)
        for name in ('armv7a-linux-androideabi24-clang',
                     'armv7a-linux-androideabi24-clang++', 'llvm-ar'):
            tool = self.bin / name
            tool.write_text('#!/bin/sh\nexit 0\n')
            tool.chmod(0o755)
        configure = self.root / 'configure'
        configure.write_text('''#!/usr/bin/env python3
import json, os, sys
with open("result.json", "w") as output:
    json.dump({"args": sys.argv[1:], "env": dict(os.environ)}, output)
sys.exit(int(os.environ.get("FAKE_CONFIGURE_EXIT", "0")))
''')
        configure.chmod(0o755)
        self.env = os.environ.copy()
        for key in ('CC', 'CXX', 'CC_target', 'CXX_target', 'CC_host',
                    'CXX_host', 'AR_target', 'LINK_target', 'GYP_DEFINES'):
            self.env.pop(key, None)

    def run_configure(self, *args):
        return subprocess.run([sys.executable, str(self.root / 'android-configure'),
                               *map(str, args)], cwd=self.root, env=self.env,
                              capture_output=True, text=True)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux NDK layout')
    def test_toolsets_and_options(self):
        self.env['CC_host'] = 'gcc -m32'
        self.env['CXX_host'] = 'g++ -m32'
        result = self.run_configure(self.ndk, '24', 'arm', '--shared',
                                    '--v8-disable-temporal-support')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads((self.root / 'result.json').read_text())
        self.assertIn('--dest-cpu=arm', data['args'])
        self.assertIn('--shared', data['args'])
        self.assertIn('--v8-disable-temporal-support', data['args'])
        self.assertEqual(data['env']['CC_host'], 'gcc -m32')
        self.assertEqual(data['env']['CXX_host'], 'g++ -m32')
        self.assertEqual(data['env']['CC_target'],
                         str(self.bin / 'armv7a-linux-androideabi24-clang'))
        self.assertEqual(data['env']['LINK_target'], data['env']['CXX_target'])
        self.assertEqual(data['env']['AR_target'], str(self.bin / 'llvm-ar'))
        import shlex
        self.assertIn('android_ndk_path=' + str(self.ndk),
                      shlex.split(data['env']['GYP_DEFINES']))

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux NDK layout')
    def test_default_host_toolset(self):
        result = self.run_configure(self.ndk, '24', 'arm')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads((self.root / 'result.json').read_text())
        if os.uname().machine in ('x86_64', 'amd64'):
            self.assertTrue(data['env']['CC_host'].endswith(' -m32'))
            self.assertTrue(data['env']['CXX_host'].endswith(' -m32'))
        self.assertEqual(data['env']['CC'], data['env']['CC_target'])

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux NDK layout')
    def test_arm64_keeps_native_host_compilers(self):
        for name in ('aarch64-linux-android24-clang',
                     'aarch64-linux-android24-clang++'):
            tool = self.bin / name
            tool.write_text('#!/bin/sh\nexit 0\n')
            tool.chmod(0o755)
        result = self.run_configure(self.ndk, '24', 'arm64')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads((self.root / 'result.json').read_text())
        self.assertIn('--dest-cpu=arm64', data['args'])
        self.assertFalse(data['env']['CC_host'].endswith(' -m32'))
        self.assertFalse(data['env']['CXX_host'].endswith(' -m32'))
        self.assertEqual(data['env']['CC_target'],
                         str(self.bin / 'aarch64-linux-android24-clang'))

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux NDK layout')
    def test_propagates_configure_failure(self):
        self.env['FAKE_CONFIGURE_EXIT'] = '23'
        result = self.run_configure(self.ndk, '24', 'arm')
        self.assertEqual(result.returncode, 23, result.stderr)

    def test_rejects_invalid_api_and_missing_ndk(self):
        spaced = self.root / 'ndk with spaces'
        spaced.mkdir()
        (spaced / 'dummy').touch()
        for ndk, api in ((self.ndk, '23'), (self.ndk, 'bad'),
                         (self.root / 'missing', '24'), (spaced, '24')):
            with self.subTest(ndk=ndk, api=api):
                self.assertNotEqual(self.run_configure(ndk, api, 'arm').returncode, 0)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux NDK layout')
    def test_missing_ndk_tool_is_an_error(self):
        (self.bin / 'llvm-ar').unlink()
        result = self.run_configure(self.ndk, '24', 'arm')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('llvm-ar', result.stderr)
        self.assertFalse((self.root / 'result.json').exists())


if __name__ == '__main__':
    unittest.main()
