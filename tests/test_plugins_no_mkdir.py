"""Read-only plugin commands must not create directories.

PluginManager.initialize() used to mkdir every configured plugin
directory, so `plugins list --directory <missing>` created the path it
was only asked to inspect, and a directory under an unwritable parent
crashed with a raw OSError traceback. Discovery already skips missing
directories; the mkdir served nothing.
"""

import os
import subprocess
import sys
from pathlib import Path


def _run_cli(*argv):
    env = dict(os.environ, PYTHONPATH=os.path.dirname(os.path.dirname(__file__)))
    return subprocess.run(
        [sys.executable, "-m", "main", *argv],
        capture_output=True, text=True, env=env, timeout=60,
    )


def test_plugins_list_does_not_create_missing_directory(tmp_path):
    missing = tmp_path / "never-existed"
    result = _run_cli("plugins", "list", "--directory", str(missing))
    assert result.returncode == 0, result.stderr
    assert not missing.exists(), "plugins list created a directory it was asked to inspect"


def test_plugins_audit_missing_directory_is_clean(tmp_path):
    missing = tmp_path / "never-existed"
    result = _run_cli("plugins", "audit", "--directory", str(missing))
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr
    assert not missing.exists()
