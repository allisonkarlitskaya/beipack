import os
import subprocess
import sys

import pytest

from bei import beipack


@pytest.fixture
def python_command() -> list[str]:
    cmd = [sys.executable]

    if 'COVERAGE_RCFILE' in os.environ:
        cmd.extend(['-m', 'coverage', 'run', '--parallel-mode'])

    return cmd


def run_pack(pack: str) -> str:
    run_process = subprocess.Popen([sys.executable, '-iq'],
                                   stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   text=True)

    stdout, stderr = run_process.communicate(pack)

    # stderr should have a lot of >>> >>> >>> >>> >>> >>> >>> ... ... ...
    assert '>>> ' in stderr
    assert '... ' in stderr
    # ... but nothing else
    if stderr.lstrip('.> \n'):
        print(stderr.lstrip('.> \n'))
        pytest.fail('Unexpected stderr')

    return stdout


def test_api() -> None:
    assert beipack.pack({}) != ''


def test_path() -> None:
    process = subprocess.run(['beipack'], capture_output=True, text=True)
    assert process.stderr == ''
    assert process.stdout != ''
    assert process.returncode == 0


def test_cmdline(python_command: list[str],
                 pytestconfig: pytest.Config) -> None:
    process = subprocess.run([
        *python_command,
        '-m', 'bei.beipack',
        '--main', 'hello:main',
        '--main-args="test"',
        '--topdir=test/files',
        'test/files/hello.py',
    ], capture_output=True, text=True, cwd=pytestconfig.rootpath)

    assert process.stderr == ''
    assert process.returncode == 0
    assert run_pack(process.stdout) == 'test world\n'


def test_resources(python_command: list[str],
                   pytestconfig: pytest.Config) -> None:
    pack = beipack.pack(
        {
            'x/subdir/__init__.py': b'',
            'x/__init__.py': b'',
            'x/y.py':
                b'# can you hear me now?\n' +
                b'from importlib import resources\n' +
                b'def main():\n'
                b'    print((resources.files("x") / "y.py").read_text())\n'
                b'    print([item.name for item in resources.files("x").iterdir()])\n'
        },
        entrypoint='x.y:main'
    )
    print(pack)
    result = run_pack(pack)
    print(result)
    assert 'can you hear me now' in result
    assert "'__init__.py'" in result
    assert "'subdir'" in result
    assert "'y.py'" in result
