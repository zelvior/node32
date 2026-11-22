#!/usr/bin/env python3
"""Validate Actions artifacts and package experimental legacy release assets."""

import argparse
import hashlib
from pathlib import Path
import re
import tarfile
import zipfile


ARTIFACTS = {
    'experimental-node-linux-x86': ('node', 'SHA256SUMS', 'tar.gz'),
    'experimental-node-windows-x86': ('node.exe', 'SHA256.txt', 'zip'),
    'experimental-node-android-armv7-executable': ('node', 'SHA256SUMS', 'tar.gz'),
    'experimental-node-android-armv7-shared': ('libnode.so', 'SHA256SUMS', 'tar.gz'),
}


def digest(path):
    hasher = hashlib.sha256()
    with path.open('rb') as file:
        for block in iter(lambda: file.read(1024 * 1024), b''):
            hasher.update(block)
    return hasher.hexdigest()


def verify_artifact(directory, binary, checksums):
    for name in (binary, 'smoke.js', 'README.txt', checksums):
        if not (directory / name).is_file():
            raise ValueError(f'Missing {directory / name}')
    if binary == 'libnode.so' and not (directory / 'include/node/node.h').is_file():
        raise ValueError('Missing Android shared library public headers')
    expected = {}
    for line in (directory / checksums).read_text(encoding='utf-8-sig').splitlines():
        match = re.fullmatch(r'([a-fA-F0-9]{64})\s+([A-Za-z0-9_.+-]+)', line)
        if not match or match.group(2) in expected:
            raise ValueError(f'Invalid checksum entry: {line!r}')
        expected[match.group(2)] = match.group(1).lower()
    required = {binary, 'smoke.js'}
    if (directory / 'libc++_shared.so').exists():
        required.add('libc++_shared.so')
    if not required.issubset(expected):
        raise ValueError(f'Missing checksums for {sorted(required - expected.keys())}')
    for name, checksum in expected.items():
        file = directory / name
        if file.is_symlink() or not file.is_file() or digest(file) != checksum:
            raise ValueError(f'Checksum mismatch or missing file: {file}')
    for file in directory.rglob('*'):
        if file.is_symlink() or not (file.is_file() or file.is_dir()):
            raise ValueError(f'Unexpected file type: {file}')


def package(input_dir, output_dir):
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    # Validate everything before creating any release assets.
    for name, (binary, checksum_file, _) in ARTIFACTS.items():
        verify_artifact(input_dir / name, binary, checksum_file)
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for name, (binary, _, extension) in ARTIFACTS.items():
        directory = input_dir / name
        output = output_dir / f'{name}.{extension}'
        files = sorted(path for path in directory.rglob('*') if path.is_file())
        if extension == 'zip':
            with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                for file in files:
                    archive.write(file, (Path(name) / file.relative_to(directory)).as_posix())
        else:
            with tarfile.open(output, 'w:gz') as archive:
                for file in files:
                    arcname = (Path(name) / file.relative_to(directory)).as_posix()
                    info = archive.gettarinfo(str(file), arcname)
                    # download-artifact does not preserve executable permissions.
                    if file == directory / binary and binary == 'node':
                        info.mode |= 0o111
                    with file.open('rb') as source:
                        archive.addfile(info, source)
        outputs.append(output)
    (output_dir / 'SHA256SUMS').write_text(
        ''.join(f'{digest(path)}  {path.name}\n' for path in outputs), encoding='ascii')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input_dir', help='directory containing downloaded artifacts')
    parser.add_argument('output_dir', help='directory for release assets')
    args = parser.parse_args()
    package(args.input_dir, args.output_dir)


if __name__ == '__main__':
    main()
