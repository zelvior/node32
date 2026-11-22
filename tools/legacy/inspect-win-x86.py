#!/usr/bin/env python3
"""Report static PE imports; this is not a Windows 7 compatibility proof.

Requires pefile. The report includes normal and delay imports, but not APIs
resolved dynamically at runtime or imports of other deployed DLLs.
"""

import argparse
import hashlib
import sys

import pefile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable')
    args = parser.parse_args()
    with open(args.executable, 'rb') as binary:
        data = binary.read()
    pe = pefile.PE(data=data)
    if pe.FILE_HEADER.Machine != 0x14c or pe.OPTIONAL_HEADER.Magic != 0x10b:
        raise SystemExit('Expected an IA-32 PE32 executable')
    print('SHA256:', hashlib.sha256(data).hexdigest())
    print('Architecture: PE32 / IA-32')
    imports = []
    for label, attr in (('normal', 'DIRECTORY_ENTRY_IMPORT'),
                        ('delay', 'DIRECTORY_ENTRY_DELAY_IMPORT')):
        for dll in getattr(pe, attr, []):
            dll_name = dll.dll.decode('ascii', errors='replace')
            for symbol in dll.imports:
                name = (symbol.name.decode('ascii', errors='replace')
                        if symbol.name is not None else f'ordinal:{symbol.ordinal}')
                imports.append((label, dll_name, name))
    if not imports:
        raise SystemExit('No imports found; refusing to treat the audit as complete')
    for label, dll, name in sorted(imports):
        print(f'{label} {dll}!{name}')
    if any(name == 'GetSystemTimePreciseAsFileTime' for _, _, name in imports):
        print('Windows 8+ precise clock is directly imported', file=sys.stderr)
        return 1
    print('Direct precise-clock import not found; further compatibility audit required.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
