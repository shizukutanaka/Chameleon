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
