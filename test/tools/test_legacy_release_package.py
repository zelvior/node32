import hashlib
import importlib.util
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    'legacy_release_package', ROOT / 'tools/legacy/package-release.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class LegacyReleasePackageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='legacy-release-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.inputs = self.root / 'inputs'
        self.outputs = self.root / 'outputs'
        for name, (binary, checksums, _) in package.ARTIFACTS.items():
            directory = self.inputs / name
            directory.mkdir(parents=True)
            (directory / binary).write_bytes(b'example binary')
            (directory / 'smoke.js').write_text('smoke')
            (directory / 'README.txt').write_text('experimental')
            if binary == 'libnode.so':
                header = directory / 'include/node/node.h'
                header.parent.mkdir(parents=True)
                header.write_text('example header')
            (directory / checksums).write_text(''.join(
                f'{hashlib.sha256((directory / filename).read_bytes()).hexdigest()}  {filename}\n'
                for filename in (binary, 'smoke.js')))

    def test_packages_all_artifacts_and_preserves_executability(self):
        package.package(self.inputs, self.outputs)
        self.assertEqual(len(list(self.outputs.iterdir())), 5)
        linux = self.outputs / 'experimental-node-linux-x86.tar.gz'
        with tarfile.open(linux) as archive:
            member = archive.getmember('experimental-node-linux-x86/node')
            self.assertEqual(member.mode & 0o111, 0o111)
            self.assertEqual(archive.extractfile(member).read(), b'example binary')
        android = self.outputs / 'experimental-node-android-armv7-executable.tar.gz'
        with tarfile.open(android) as archive:
            self.assertEqual(archive.getmember(
                'experimental-node-android-armv7-executable/node').mode & 0o111, 0o111)
        shared = self.outputs / 'experimental-node-android-armv7-shared.tar.gz'
        with tarfile.open(shared) as archive:
            self.assertIn('experimental-node-android-armv7-shared/include/node/node.h',
                          archive.getnames())
        windows = self.outputs / 'experimental-node-windows-x86.zip'
        with zipfile.ZipFile(windows) as archive:
            self.assertEqual(archive.read('experimental-node-windows-x86/node.exe'),
                             b'example binary')
        checksums = (self.outputs / 'SHA256SUMS').read_text()
        for file in (linux, android, shared, windows):
            self.assertIn(f'{package.digest(file)}  {file.name}', checksums)

    def test_missing_or_corrupted_artifact_fails_before_packaging(self):
        (self.inputs / 'experimental-node-linux-x86/node').write_bytes(b'corrupted')
        with self.assertRaises(ValueError):
            package.package(self.inputs, self.outputs)
        self.assertFalse(self.outputs.exists())

    def test_missing_artifact_fails_before_packaging(self):
        (self.inputs / 'experimental-node-windows-x86/node.exe').unlink()
        with self.assertRaises(ValueError):
            package.package(self.inputs, self.outputs)
        self.assertFalse(self.outputs.exists())

    def test_missing_android_headers_fails(self):
        (self.inputs / 'experimental-node-android-armv7-shared/include/node/node.h').unlink()
        with self.assertRaises(ValueError):
            package.package(self.inputs, self.outputs)

    def test_android_cxx_runtime_requires_checksum_and_is_packaged(self):
        directory = self.inputs / 'experimental-node-android-armv7-executable'
        runtime = directory / 'libc++_shared.so'
        runtime.write_bytes(b'runtime')
        with self.assertRaises(ValueError):
            package.package(self.inputs, self.outputs)
        with (directory / 'SHA256SUMS').open('a') as checksums:
            checksums.write(f'{package.digest(runtime)}  {runtime.name}\n')
        package.package(self.inputs, self.outputs)
        with tarfile.open(self.outputs / 'experimental-node-android-armv7-executable.tar.gz') as archive:
            self.assertIn('experimental-node-android-armv7-executable/libc++_shared.so',
                          archive.getnames())

    @unittest.skipIf(os.name == 'nt', 'Creating symlinks may require Windows privileges')
    def test_symlink_in_artifact_rejected(self):
        directory = self.inputs / 'experimental-node-linux-x86'
        (directory / 'extra').symlink_to(directory / 'node')
        with self.assertRaises(ValueError):
            package.package(self.inputs, self.outputs)

    def test_checksum_path_traversal_rejected(self):
        (self.inputs / 'experimental-node-linux-x86/SHA256SUMS').write_text(
            '0' * 64 + '  ../outside\n')
        with self.assertRaises(ValueError):
            package.package(self.inputs, self.outputs)


if __name__ == '__main__':
    unittest.main()
