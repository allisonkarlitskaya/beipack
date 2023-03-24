import os
import subprocess
import sys
import tempfile


def main(*command: str) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        os.chdir(tmpdir)

        for key, value in __loader__.get_contents().items():
            if key.startswith('tmpfs/'):
                subdir = os.path.dirname(key)
                os.makedirs(subdir, exist_ok=True)
                with open(key, 'wb') as fp:
                    fp.write(value)

        os.chdir('tmpfs')

        result = subprocess.run(command, check=False)
        sys.exit(result.returncode)
