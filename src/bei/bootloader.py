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
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

GADGETS = {
    "_frame": r"""
        import sys
        import traceback
        try:
            ...
        except SystemExit:
            raise
        except BaseException:
            command('beiboot.exc', traceback.format_exc())
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
            command('beiboot.provide', size)
            src_xz = sys.stdin.buffer.read(size)
            src = lzma.decompress(src_xz)
            sys.argv = [filename, *args]
            if send_end:
                end()
            exec(src, {
                '__name__': '__main__',
                '__self_source__': src_xz,
                '__file__': filename})
            sys.exit()
    """,
}


def split_code(code: str, imports: Set[str]) -> Iterable[Tuple[str, str]]:
    for line in textwrap.dedent(code).splitlines():
        text = line.lstrip(" ")
        if text.startswith("import "):
            imports.add(text)
        elif text:
            spaces = len(line) - len(text)
            assert (spaces % 4) == 0
            yield "\t" * (spaces // 4), text


def yield_body(user_gadgets: Dict[str, str],
               steps: Sequence[Tuple[str, Sequence[object]]],
               imports: Set[str]) -> Iterable[Tuple[str, str]]:
    # Allow the caller to override our gadgets, but keep the original
    # variable for use in the next step.
    gadgets = dict(GADGETS, **user_gadgets)

    # First emit the gadgets.  Emit all gadgets provided by the caller,
    # plus any referred to by the caller's list of steps.
    provided_gadgets = set(user_gadgets)
    step_gadgets = {name for name, _args in steps}
    for name in provided_gadgets | step_gadgets:
        yield from split_code(gadgets[name], imports)

    # Yield functions mentioned in steps from the caller
    for name, args in steps:
        yield '', name + repr(tuple(args))


def make_bootloader(steps: Sequence[Tuple[str, Sequence[object]]],
                    gadgets: Optional[Dict[str, str]] = None) -> str:
    imports: Set[str] = set()
    lines: List[str] = []

    for frame_spaces, frame_text in split_code(GADGETS["_frame"], imports):
        if frame_text == "...":
            for spaces, text in yield_body(gadgets or {}, steps, imports):
                lines.append(frame_spaces + spaces + text)
        else:
            lines.append(frame_spaces + frame_text)

    return "".join(f"{line}\n" for line in [*imports, *lines]) + "\n"
