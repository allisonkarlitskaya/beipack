# beipack - Remote bootloader for Python
#
# Copyright (C) 2022 Allison Karlitskaya <allison.karlitskaya@redhat.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import binascii
import lzma
import os
import sys
import tempfile
import zipfile
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .data import read_data_file


def escape_string(data: str) -> str:
    # Avoid mentioning ' ' ' literally, to make our own packing a bit prettier
    triplequote = "'" * 3
    if triplequote not in data:
        return "r" + triplequote + data + triplequote
    if '"""' not in data:
        return 'r"""' + data + '"""'
    return repr(data)


def ascii_bytes_repr(data: bytes) -> str:
    return 'b' + escape_string(data.decode('ascii'))


def utf8_bytes_repr(data: bytes) -> str:
    return escape_string(data.decode('utf-8')) + ".encode('utf-8')"


def base64_bytes_repr(data: bytes, imports: Set[str]) -> str:
    # base85 is smaller, but base64 is in C, and ~20x faster.
    # when compressing with `xz -e` the size difference is marginal.
    imports.add('from binascii import a2b_base64')
    encoded = binascii.b2a_base64(data).decode('ascii').strip()
    return f'a2b_base64("{encoded}")'


def bytes_repr(data: bytes, imports: Set[str]) -> str:
    # Strategy:
    #   if the file is ascii, encode it directly as bytes
    #   otherwise, if it's UTF-8, use a unicode string and encode
    #   otherwise, base64

    try:
        return ascii_bytes_repr(data)
    except UnicodeDecodeError:
        # it's not ascii
        pass

    # utf-8
    try:
        return utf8_bytes_repr(data)
    except UnicodeDecodeError:
        # it's not utf-8
        pass

    return base64_bytes_repr(data, imports)


def dict_repr(contents: Dict[str, bytes], imports: Set[str]) -> str:
    return ('{\n' +
            ''.join(f'  {repr(k)}: {bytes_repr(v, imports)},\n'
                    for k, v in contents.items()) +
            '}')


def pack(contents: Dict[str, bytes],
         entrypoint: Optional[str] = None,
         args: str = '') -> str:
    """Creates a beipack with the given `contents`.

    If `entrypoint` is given, it should be an entry point which is run as the
    "main" function.  It is given in the `package.module:func format` such that
    the following code is emitted:

        from package.module import func as main
        main()

    Additionally, if `args` is given, it is written verbatim between the parens
    of the call to main (ie: it should already be in Python syntax).
    """

    loader = read_data_file('beipack_loader.py')
    lines = [line for line in loader.splitlines() if line]
    lines.append('')

    imports = {'import sys'}
    contents_txt = dict_repr(contents, imports)
    lines.extend(imports)
    lines.append(f'sys.meta_path.insert(0, BeipackLoader({contents_txt}))')

    if entrypoint:
        package, main = entrypoint.split(':')
        lines.append(f'from {package} import {main} as main')
        lines.append(f'main({args})')

    return ''.join(f'{line}\n' for line in lines)


def collect_contents(filenames: List[str],
                     relative_to: Optional[str] = None) -> Dict[str, bytes]:
    contents: Dict[str, bytes] = {}

    for filename in filenames:
        with open(filename, 'rb') as file:
            contents[os.path.relpath(filename, start=relative_to)] = file.read()

    return contents


def collect_module(name: str, *, recursive: bool) -> Dict[str, bytes]:
    import importlib.resources
    from importlib.resources.abc import Traversable

    def walk(path: str, entry: Traversable) -> Iterable[Tuple[str, bytes]]:
        for item in entry.iterdir():
            itemname = f'{path}/{item.name}'
            if item.is_file():
                yield itemname, item.read_bytes()
            elif recursive and item.name != '__pycache__':
                yield from walk(itemname, item)

    return dict(walk(name.replace('.', '/'), importlib.resources.files(name)))


def collect_zip(filename: str) -> Dict[str, bytes]:
    contents = {}

    with zipfile.ZipFile(filename) as file:
        for entry in file.filelist:
            if '.dist-info/' in entry.filename:
                continue
            contents[entry.filename] = file.read(entry)

    return contents


def collect_pep517(path: str) -> Dict[str, bytes]:
    with tempfile.TemporaryDirectory() as tmpdir:
        import build
        builder = build.ProjectBuilder(path)
        wheel = builder.build('wheel', tmpdir)
        return collect_zip(wheel)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--python', '-p',
                        help="add a #!python3 interpreter line using the given path")
    parser.add_argument('--xz', '-J', action='store_true',
                        help="compress the output with `xz`")
    parser.add_argument('--topdir',
                        help="toplevel directory (paths are stored relative to this)")
    parser.add_argument('--output', '-o',
                        help="write output to a file (default: stdout)")
    parser.add_argument('--main', '-m', metavar='MODULE:FUNC',
                        help="use FUNC from MODULE as the main function")
    parser.add_argument('--main-args', metavar='ARGS',
                        help="arguments to main() in Python syntax", default='')
    parser.add_argument('--module', action='append', default=[],
                        help="collect installed modules (recursively)")
    parser.add_argument('--zip', '-z', action='append', default=[],
                        help="include files from a zipfile (or wheel)")
    parser.add_argument('--build', metavar='DIR', action='append', default=[],
                        help="PEP-517 from a given source directory")
    parser.add_argument('files', nargs='*',
                        help="files to include in the beipack")
    args = parser.parse_args()

    contents = collect_contents(args.files, relative_to=args.topdir)

    for file in args.zip:
        contents.update(collect_zip(file))

    for name in args.module:
        contents.update(collect_module(name, recursive=True))

    for path in args.build:
        contents.update(collect_pep517(path))

    result = pack(contents, args.main, args.main_args).encode('utf-8')

    if args.python:
        result = b'#!' + args.python.encode('ascii') + b'\n' + result

    if args.xz:
        result = lzma.compress(result, preset=lzma.PRESET_EXTREME)

    if args.output:
        with open(args.output, 'wb') as file:
            file.write(result)
    else:
        if args.xz and os.isatty(1):
            sys.exit('refusing to write compressed output to a terminal')
        sys.stdout.buffer.write(result)


if __name__ == '__main__':
    main()
