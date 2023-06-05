# beiboot - Remote bootloader for Python
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
import asyncio
import os
import shlex
import subprocess
import sys
import threading
from typing import IO, List, Sequence, Tuple

from .bootloader import make_bootloader


def get_python_command(local: bool = False,
                       tty: bool = False,
                       sh: bool = False) -> Sequence[str]:
    interpreter = sys.executable if local else 'python3'
    command: Sequence[str]

    if tty:
        command = (interpreter, '-iq')
    else:
        command = (
            interpreter, '-ic',
            # https://github.com/python/cpython/issues/93139
            '''" - beiboot - "; import sys; sys.ps1 = ''; sys.ps2 = '';'''
        )

    if sh:
        command = (' '.join(shlex.quote(arg) for arg in command),)

    return command


def get_ssh_command(*args: str, tty: bool = False) -> Sequence[str]:
    return ('ssh',
            *(['-t'] if tty else ()),
            *args,
            *get_python_command(tty=tty, sh=True))


def get_container_command(*args: str, tty: bool = False) -> Sequence[str]:
    return ('podman', 'exec', '--interactive',
            *(['--tty'] if tty else ()),
            *args,
            *get_python_command(tty=tty))


def get_command(*args: str, tty: bool = False, sh: bool = False) -> Sequence[str]:
    return (*args, *get_python_command(local=True, tty=tty, sh=sh))


def splice_in_thread(src: int, dst: IO[bytes]) -> None:
    def _thread() -> None:
        # os.splice() only in Python 3.10
        with dst:
            block_size = 1 << 20
            while True:
                data = os.read(src, block_size)
                if not data:
                    break
                dst.write(data)
                dst.flush()

    threading.Thread(target=_thread, daemon=True).start()


def send_and_splice(command: Sequence[str], script: bytes) -> None:
    with subprocess.Popen(command, stdin=subprocess.PIPE) as proc:
        assert proc.stdin is not None
        proc.stdin.write(script)

        splice_in_thread(0, proc.stdin)
        sys.exit(proc.wait())


def send_xz_and_splice(command: Sequence[str], script: bytes) -> None:
    import ferny

    class Responder(ferny.InteractionResponder):
        async def do_custom_command(self,
                                    command: str,
                                    args: Tuple,
                                    fds: List[int],
                                    stderr: str) -> None:
            assert proc.stdin is not None
            if command == 'beiboot.provide':
                proc.stdin.write(script)
                proc.stdin.flush()

    agent = ferny.InteractionAgent(Responder())
    with subprocess.Popen(command, stdin=subprocess.PIPE, stderr=agent) as proc:
        assert proc.stdin is not None
        proc.stdin.write(make_bootloader([
            ('boot_xz', ('script.py.xz', len(script), [], True)),
        ], gadgets=ferny.BEIBOOT_GADGETS).encode())
        proc.stdin.flush()

        asyncio.run(agent.communicate())
        splice_in_thread(0, proc.stdin)
        sys.exit(proc.wait())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--sh', action='store_true',
                        help='Pass Python interpreter command as shell-script')
    parser.add_argument('--xz', help="the xz to run remotely")
    parser.add_argument('--script',
                        help="the script to run remotely (must be repl-friendly)")
    parser.add_argument('command', nargs='*')

    args = parser.parse_args()
    tty = not args.script and os.isatty(0)

    if args.command == []:
        command = get_python_command(tty=tty)
    elif args.command[0] == 'ssh':
        command = get_ssh_command(*args.command[1:], tty=tty)
    elif args.command[0] == 'container':
        command = get_container_command(*args.command[1:], tty=tty)
    else:
        command = get_command(*args.command, tty=tty, sh=args.sh)

    if args.script:
        with open(args.script, 'rb') as file:
            script = file.read()

        send_and_splice(command, script)

    elif args.xz:
        with open(args.xz, 'rb') as file:
            script = file.read()

        send_xz_and_splice(command, script)

    else:
        # If we're streaming from stdin then this is a lot easier...
        os.execlp(command[0], *command)

    # Otherwise, "full strength"

if __name__ == '__main__':
    main()
