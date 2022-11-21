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
import string
import sys
import zipfile

from typing import Optional


def escape_string(data: str) -> str:
    if "'''" not in data:
        return "r'''" + data + "'''"
    if '"""' not in data:
        return 'r"""' + data + '"""'
    return repr(data)


def ascii_bytes_repr(data: bytes) -> str:
    return 'b' + escape_string(data.decode('ascii'))


def utf8_bytes_repr(data: bytes) -> str:
    return escape_string(data.decode('utf-8')) + ".encode('utf-8')"


def base64_bytes_repr(data: bytes) -> str:
    # base85 is smaller, but base64 is in C, and ~20x faster.
    # when compressing with `xz -e` the size difference is marginal.
    encoded = binascii.b2a_base64(data).decode('ascii').strip()
    return f'a2b_base64("{encoded}")'


def bytes_repr(data: bytes) -> str:
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

    return base64_bytes_repr(data)


def dict_repr(contents: dict[str, bytes]) -> str:
    return '{\n' + ''.join(f'  {repr(k)}: {bytes_repr(v)},\n' for k, v in contents.items()) + '}'


def pack(contents: dict[str, bytes], entrypoint: Optional[str], template: Optional[str] = None) -> str:
    if template is None:
        with open(os.path.realpath(f'{__file__}/../beipack.py.template')) as file:
            template = ''.join(line for line in file if line.strip())

    result = string.Template(template).substitute(contents=dict_repr(contents))

    result += '\nsys.meta_path.insert(0, BeipackLoader())\n'

    if entrypoint:
        package, main = entrypoint.split(':')
        result += f'from {package} import {main} as main\nmain()\n'

    return result


def collect_contents(filenames: list[str], relative_to: Optional[str] = None) -> dict[str, bytes]:
    contents: dict[str, bytes] = {}

    for filename in filenames:
        with open(filename, 'rb') as file:
            contents[os.path.relpath(filename, start=relative_to)] = file.read()

    return contents


def collect_zip(filename: str) -> dict[str, bytes]:
    contents = {}

    with zipfile.ZipFile(filename) as file:
        for entry in file.filelist:
            contents[entry.filename] = file.read(entry)

    return contents


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--xz', '-J', action='store_true', help="compress the output with `xz`")
    parser.add_argument('--topdir', help="toplevel directory (ie: all paths are stored relative to this)")
    parser.add_argument('--output', '-o', help="write output to a file (default: stdout)")
    parser.add_argument('--main', '-m', metavar='MODULE:FUNC', help="use FUNC from MODULE as the main function")
    parser.add_argument('--zip', '-z', action='append', default=[], help="include files from a zipfile (or wheel)")
    parser.add_argument('files', nargs='*', help="files to include in the beipack")
    args = parser.parse_args()

    contents = collect_contents(args.files, relative_to=args.topdir)

    for file in args.zip:
        contents.update(collect_zip(file))

    result = pack(contents, args.main).encode('utf-8')

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
