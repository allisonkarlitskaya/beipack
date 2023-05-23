# beiboot - Remote bootloader for Python
#
# Copyright (C) 2023 Allison Karlitskaya <allison.karlitskaya@redhat.com>
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

import textwrap
from typing import Iterable, List, Sequence, Set, Tuple

import ferny

STEP = {
    "_frame": rf"""
        import sys
        import traceback
        try:
            def ferny(command, *args):
                sys.stderr.write(f{ferny.COMMAND_TEMPLATE!r})
                sys.stderr.flush()
            ...
        except SystemExit:
            raise
        except BaseException:
            ferny('beiboot.exc', traceback.format_exc())
            sys.exit(37)
    """,
    "try_exec": r"""
        import contextlib
        import os
        def try_exec(argv):
            with contextlib.suppress(OSError):
                os.execvp(argv[0], argv)
    """,
    "boot_xz": r"""
        import lzma
        import sys
        def boot_xz(filename, size, args=[], send_end=False):
            ferny('beiboot.provide', size)
            src_xz = sys.stdin.buffer.read(size)
            src = lzma.decompress(src_xz)
            sys.argv = [filename, *args]
            if send_end:
                ferny('ferny.end')
            exec(src, {
                '__name__': '__main__',
                '__source_xz__': src_xz,
                '__file__': filename})
            sys.exit()
    """,
}


def get_code(name: str, imports: Set[str]) -> Iterable[Tuple[str, str]]:
    for line in textwrap.dedent(STEP[name]).splitlines():
        text = line.lstrip(" ")
        if text.startswith("import "):
            imports.add(text)
        elif text:
            spaces = len(line) - len(text)
            assert (spaces % 4) == 0
            yield "\t" * (spaces // 4), text


def make_bootloader(steps: Sequence[Tuple[str, Sequence[object]]]) -> str:
    imports: Set[str] = set()
    lines: List[str] = []

    for frame_spaces, frame_text in get_code("_frame", imports):
        if frame_text == "...":
            for name, args in steps:
                for spaces, text in get_code(name, imports):
                    lines.append(frame_spaces + spaces + text)
                lines.append(frame_spaces + name + repr(tuple(args)))
        else:
            lines.append(frame_spaces + frame_text)

    return "".join(f"{line}\n" for line in [*imports, *lines]) + "\n"
