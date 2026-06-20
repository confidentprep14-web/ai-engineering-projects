"""Confirms DATABASE_PATH defaults to /tmp — the only writable path on Lambda.

This imports src.config in a subprocess with a clean environment so the
module-level default is evaluated fresh, independent of whatever
DATABASE_PATH other test files may have already set via os.environ.
"""
import subprocess
import sys


def test_database_path_defaults_to_tmp_when_unset():
    script = (
        "import os; "
        "os.environ.pop('DATABASE_PATH', None); "
        "os.environ.pop('AWS_LAMBDA_FUNCTION_NAME', None); "
        "from src.config import config; "
        "print(config.database_path)"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=__file__.rsplit("/tests/", 1)[0],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "/tmp/chat_requests.db"


def test_database_path_respects_explicit_env_override():
    script = (
        "import os; "
        "os.environ['DATABASE_PATH'] = '/tmp/custom_override.db'; "
        "from src.config import config; "
        "print(config.database_path)"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=__file__.rsplit("/tests/", 1)[0],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "/tmp/custom_override.db"
