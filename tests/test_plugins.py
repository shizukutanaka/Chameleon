"""Tests for the plugin sandbox security checks."""

from pathlib import Path

import pytest

from plugin_system import PluginSandbox, PluginConfig, PluginLoader
from security_validator import SecurityError


def test_sandbox_blocks_restricted_imports():
    sandbox = PluginSandbox(PluginConfig())

    assert sandbox.is_safe_import("os") is False
    assert sandbox.is_safe_import("subprocess") is False
    assert sandbox.is_safe_import("socket") is False


def test_sandbox_allows_safe_imports():
    sandbox = PluginSandbox(PluginConfig())

    assert sandbox.is_safe_import("math") is True
    assert sandbox.is_safe_import("json") is True


def test_check_module_safety_rejects_unsafe_plugin(tmp_path):
    loader = PluginLoader(PluginConfig())
    bad = tmp_path / "bad_plugin.py"
    bad.write_text("import os\nos.system('echo hi')\n")

    with pytest.raises(SecurityError, match="Unsafe import"):
        loader._check_module_safety(Path(bad))


def test_check_module_safety_accepts_safe_plugin(tmp_path):
    loader = PluginLoader(PluginConfig())
    good = tmp_path / "good_plugin.py"
    good.write_text("import math\n\n\ndef process(x):\n    return math.sqrt(x)\n")

    # Should not raise.
    loader._check_module_safety(Path(good))


def test_check_module_safety_rejects_invalid_syntax(tmp_path):
    loader = PluginLoader(PluginConfig())
    broken = tmp_path / "broken_plugin.py"
    broken.write_text("def oops(:\n")

    with pytest.raises(SecurityError, match="invalid syntax"):
        loader._check_module_safety(Path(broken))


# -- sandbox bypass regressions -----------------------------------------
#
# The AST check originally only walked ast.Import/ast.ImportFrom nodes, so a
# plugin using the always-available __import__ builtin (no `import` statement
# at all) loaded and executed unrestricted code at exec_module() time —
# verified empirically before this fix landed. These pin the specific
# bypasses that are now caught.

def test_check_module_safety_rejects_dunder_import_call(tmp_path):
    loader = PluginLoader(PluginConfig())
    bad = tmp_path / "bypass1.py"
    bad.write_text('_os = __import__("os")\n_os.system("echo hi")\n')

    with pytest.raises(SecurityError, match="Unsafe call detected: __import__"):
        loader._check_module_safety(Path(bad))


def test_check_module_safety_rejects_importlib_import_module(tmp_path):
    loader = PluginLoader(PluginConfig())
    bad = tmp_path / "bypass2.py"
    bad.write_text('import importlib\n_os = importlib.import_module("os")\n')

    with pytest.raises(SecurityError, match="Unsafe call detected: importlib.import_module"):
        loader._check_module_safety(Path(bad))


@pytest.mark.parametrize("call", ["eval('1+1')", "exec('x=1')", "compile('1', '<s>', 'eval')"])
def test_check_module_safety_rejects_eval_exec_compile(tmp_path, call):
    loader = PluginLoader(PluginConfig())
    bad = tmp_path / "bypass3.py"
    bad.write_text(call + "\n")

    with pytest.raises(SecurityError, match="Unsafe call detected"):
        loader._check_module_safety(Path(bad))


def test_check_module_safety_rejects_dunder_globals_access(tmp_path):
    loader = PluginLoader(PluginConfig())
    bad = tmp_path / "bypass4.py"
    bad.write_text("def f():\n    pass\nx = f.__globals__\n")

    with pytest.raises(SecurityError, match="Unsafe attribute access"):
        loader._check_module_safety(Path(bad))


def test_check_module_safety_still_accepts_safe_plugin_after_hardening(tmp_path):
    """Regression guard: the new checks must not false-positive on ordinary
    code that merely calls unrelated functions or uses normal attributes."""
    loader = PluginLoader(PluginConfig())
    good = tmp_path / "still_good.py"
    good.write_text(
        "import math\n\n\ndef process(x):\n    return math.sqrt(abs(x))\n"
    )

    loader._check_module_safety(Path(good))  # must not raise
