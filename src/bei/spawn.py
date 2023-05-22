"""Helper to create a beipack to spawn a command with files in a tmpdir"""

import argparse
import os
import sys

from . import pack, tmpfs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', '-f', action='append')
    parser.add_argument('command', nargs='+', help='The command to execute')
    args = parser.parse_args()

    contents = {
        '_beitmpfs.py': tmpfs.__spec__.loader.get_data(tmpfs.__spec__.origin)
    }

    if args.file is not None:
        files = args.file
    else:
        file = args.command[-1]
        files = [file]
        args.command[-1] = './' + os.path.basename(file)

    for filename in files:
        with open(filename, 'rb') as file:
            basename = os.path.basename(filename)
            contents[f'tmpfs/{basename}'] = file.read()

    script = pack.pack(contents, '_beitmpfs:main', '*' + repr(args.command))
    sys.stdout.write(script)


if __name__ == '__main__':
    main()
