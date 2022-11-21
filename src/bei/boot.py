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
import subprocess
import os
import sys

from typing import Optional


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('script',
                        help="the script to run remotely (must be repl-friendly)")
    parser.add_argument('command', nargs='*',
                        help="the command to connect to the remote (like 'ssh host' or 'flatpak-spawn --host')")
    args = parser.parse_args()

    with open(args.script, 'rb') as file:
        script = file.read()

    with subprocess.Popen([*args.command, 'python3', '-i'], stdin=subprocess.PIPE) as proc:
        assert proc.stdin is not None
        proc.stdin.write(script)

        # This is not exactly transparent behaviour: it models a form of
        # communication where we send commands to the remote, followed by EOF,
        # and then wait for the remote to exit.  If the program invoking us is
        # waiting for the remote to exit first, this might deadlock.
        while True:
            data = os.read(0, 1024*1024)
            if data == b'':
                proc.stdin.close()
                break

            proc.stdin.write(data)

        sys.exit(proc.wait())


if __name__ == '__main__':
    main()
