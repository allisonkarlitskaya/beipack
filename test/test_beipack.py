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


def test_api() -> None:
    assert beipack.pack({}) != ''


def test_path() -> None:
    process = subprocess.run(['beipack'], capture_output=True, text=True)
    assert process.stderr == ''
    assert process.stdout != ''
    assert process.returncode == 0


def test_cmdline(python_command: list[str],
                 capsys: pytest.CaptureFixture,
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

    exec(process.stdout, {})

    captured = capsys.readouterr()
    assert captured.out == "test world\n"
