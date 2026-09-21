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


@pytest.mark.parametrize(
    "module",
    ["pathlib", "shutil", "io", "ctypes", "gc", "inspect", "threading",
     "logging", "sqlite3", "importlib", "wave", "pickle", "mmap"],
)
def test_sandbox_import_policy_is_deny_by_default(module):
    """A blocklist names what is dangerous and admits everything else;
    `import pathlib` wrote a file with zero flagged constructs before
    the policy was inverted (verified end to end)."""
    sandbox = PluginSandbox(PluginConfig())
    assert sandbox.is_safe_import(module) is False


@pytest.mark.parametrize(
    "attr",
    ["__traceback__", "tb_frame", "f_globals", "f_builtins", "f_locals",
     "f_back", "gi_frame", "cr_frame", "ag_frame"],
)
def test_check_module_safety_rejects_frame_reaching_attrs(tmp_path, attr):
    """e.__traceback__.tb_frame.f_globals reaches __builtins__ with no
    import at all -- the probe plugin passed audit before these names
    joined the blocked-attribute set."""
    loader = PluginLoader(PluginConfig())
    bad = tmp_path / "bypass_frame.py"
    bad.write_text(f"def f(e):\n    return e.{attr}\n")

    with pytest.raises(SecurityError, match="Unsafe attribute access"):
        loader._check_module_safety(Path(bad))


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

    # `importlib` is off the import allowlist, so the Import node is
    # rejected before the import_module attribute call is ever inspected.
    with pytest.raises(SecurityError, match="Unsafe import detected: importlib"):
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


@pytest.mark.parametrize(
    "attr",
    ["__dict__", "__class__", "__base__", "__code__", "__getattribute__", "__func__", "__self__"],
)
def test_check_module_safety_rejects_introspection_dunders(tmp_path, attr):
    loader = PluginLoader(PluginConfig())
    bad = tmp_path / "bypass_introspect.py"
    bad.write_text(f"x = (0).{attr}\n")

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


def test_check_module_safety_rejects_aliased_eval(tmp_path):
    # `e = eval; e("...")` never puts `eval` in Call position, so a
    # Call-only check misses it. Verified: this shape passed the audit.
    loader = PluginLoader(PluginConfig())
    bad = tmp_path / "alias.py"
    bad.write_text('_e = eval\n_e("import os")\n')

    with pytest.raises(SecurityError, match="Unsafe reference detected: eval"):
        loader._check_module_safety(Path(bad))


def test_check_module_safety_rejects_getattr_on_builtins_name(tmp_path):
    # getattr(__builtins__, "ev" + "al") was verified to load and audit-PASS
    # before dynamic/computed getattr names were rejected.
    loader = PluginLoader(PluginConfig())
    bad = tmp_path / "getattr_concat.py"
    bad.write_text('f = getattr(__builtins__, "ev" + "al")\nf("1")\n')

    with pytest.raises(SecurityError):
        loader._check_module_safety(Path(bad))


def test_check_module_safety_rejects_getattr_with_literal_dunder(tmp_path):
    loader = PluginLoader(PluginConfig())
    bad = tmp_path / "getattr_dunder.py"
    bad.write_text('f = getattr(object(), "__subclasses__")\n')

    with pytest.raises(SecurityError, match="Unsafe getattr"):
        loader._check_module_safety(Path(bad))


@pytest.mark.parametrize("call", ["globals()", "locals()", "vars()"])
def test_check_module_safety_rejects_namespace_dict_calls(tmp_path, call):
    # globals()/locals()/vars() return a live namespace dict, reaching
    # __builtins__ with no attribute access the walk can see.
    loader = PluginLoader(PluginConfig())
    bad = tmp_path / "nsdict.py"
    bad.write_text(f"ns = {call}\n")

    with pytest.raises(SecurityError, match="Unsafe call detected"):
        loader._check_module_safety(Path(bad))


@pytest.mark.parametrize("name", ["open", "input", "breakpoint", "exit", "quit"])
def test_check_module_safety_rejects_dangerous_builtins(tmp_path, name):
    # Builtins need no import: a bare open("/tmp/x","w") escaped the sandbox
    # entirely (wrote a real file) while every import was audited.
    loader = PluginLoader(PluginConfig())
    bad = tmp_path / "bad.py"
    bad.write_text(f'{name}("x")\n')
    with pytest.raises(SecurityError, match="Unsafe (call|reference)"):
        loader._check_module_safety(Path(bad))


def test_check_module_safety_rejects_aliased_open(tmp_path):
    # `w = open; w(...)` never puts "open" in Call position -- the
    # referenced-name check has to catch the alias.
    loader = PluginLoader(PluginConfig())
    bad = tmp_path / "bad.py"
    bad.write_text('w = open\nw("/tmp/x", "w")\n')
    with pytest.raises(SecurityError, match="Unsafe reference"):
        loader._check_module_safety(Path(bad))


def test_plugins_list_json_reports_load_failures(tmp_path):
    """A plugin file that fails to load used to vanish from `plugins list
    --json` -- `"plugins": {}` can't distinguish "empty directory" from
    "everything failed". Machine consumers need the failures named."""
    import json
    import subprocess
    import sys
    from pathlib import Path
    main_py = str(Path(__file__).resolve().parent.parent / "main.py")

    (tmp_path / "bad.py").write_text("import os\nx = os\n")
    out = subprocess.run(
        [sys.executable, main_py, "plugins", "list",
         "--directory", str(tmp_path), "--json"],
        capture_output=True, text=True, timeout=30)
    assert out.returncode == 0
    payload = json.loads(out.stdout[out.stdout.index("{"):])
    failures = payload.get("load_failures", {})
    assert any("bad.py" in path for path in failures)
    # The failure reason must carry the sandbox's specific verdict, not the
    # generic "no valid plugin class" -- a sandbox rejection is a security
    # event, a broken plugin is an authoring bug; consumers can't distinguish
    # them from the generic message.
    reason = next(r for p, r in failures.items() if "bad.py" in p)
    assert "Unsafe import" in reason


def test_load_plugin_initialize_timeout_is_reported_not_swallowed(tmp_path):
    """initialize() is plugin code: a sleeping/hung plugin used to run
    unbounded (verified: `plugins list` needed SIGTERM on a sleep(120)
    plugin). The sandbox's time limit must wrap it, and the timeout must
    reach load_failures as a TimeoutError, not collapse to a generic
    'no valid plugin class'."""
    import time
    loader = PluginLoader(PluginConfig(max_execution_time=1))
    slow = tmp_path / "slow_init.py"
    slow.write_text(
        "import time\n"
        "from plugin_system import AudioEffectPlugin, PluginMetadata\n"
        "class Slow(AudioEffectPlugin):\n"
        "    def get_metadata(self):\n"
        "        return PluginMetadata(name='s', version='1.0.0', author='t',\n"
        "                              description='t', category='effect')\n"
        "    def initialize(self, config):\n"
        "        time.sleep(30)\n"
        "        return True\n"
        "    def cleanup(self):\n"
        "        pass\n"
        "    def process_audio(self, audio_data, sample_rate, **params):\n"
        "        return audio_data\n"
    )

    t0 = time.monotonic()
    with pytest.raises(TimeoutError, match="timed out"):
        loader.load_plugin(slow)
    assert time.monotonic() - t0 < 10


@pytest.mark.parametrize("hang_site", ["module", "init", "metadata"])
def test_load_plugin_limits_all_plugin_code_sites(tmp_path, hang_site):
    """Every plugin-defined callable on the load path runs inside the
    sandbox's time limit -- module top level, __init__, get_metadata and
    initialize. Until the wrap, only execute_plugin() was bounded; a
    sleep in any of the others hung `plugins list` (verified)."""
    import time
    loader = PluginLoader(PluginConfig(max_execution_time=1))
    body = "import time\n" + ("time.sleep(30)\n" if hang_site == "module" else "")
    init_sleep = "        time.sleep(30)\n" if hang_site == "init" else "        return True\n"
    meta_sleep = "        time.sleep(30)\n" if hang_site == "metadata" else ""
    plugin = tmp_path / "hanging.py"
    plugin.write_text(
        body +
        "from plugin_system import AudioEffectPlugin, PluginMetadata\n"
        "class H(AudioEffectPlugin):\n"
        "    def get_metadata(self):\n" + meta_sleep +
        "        return PluginMetadata(name='h', version='1.0.0', author='t',\n"
        "                              description='t', category='effect')\n"
        "    def initialize(self, config):\n" + init_sleep +
        "    def cleanup(self):\n"
        "        pass\n"
        "    def process_audio(self, audio_data, sample_rate, **params):\n"
        "        return audio_data\n"
    )

    t0 = time.monotonic()
    with pytest.raises(TimeoutError, match="timed out"):
        loader.load_plugin(plugin)
    assert time.monotonic() - t0 < 10


def test_load_plugin_executes_the_bytes_it_scanned(tmp_path):
    """The AST scan and module execution must see identical bytes -- a file
    swapped between the scan's read and exec's re-read would run unscanned
    code."""
    plugin = tmp_path / "swapped.py"
    plugin.write_text(
        "from plugin_system import AudioEffectPlugin, PluginMetadata\n"
        "MARKER = 'scanned-version'\n"
        "class P(AudioEffectPlugin):\n"
        "    def get_metadata(self):\n"
        "        return PluginMetadata(name='p', version='1.0.0', author='t',\n"
        "                              description='d', category='effect')\n"
        "    def initialize(self, config): return True\n"
        "    def cleanup(self): pass\n"
        "    def process_audio(self, a, sr, **kw): return a\n"
        "    def analyze_audio(self, a, sr, **kw): return {}\n"
    )
    loader = PluginLoader(PluginConfig(plugin_directories=[str(tmp_path)]))

    # Swap in hostile content between the scan and any second read; with a
    # single read the executed module is still the scanned version.
    real_check = loader._check_module_safety
    def swap_then_check(source, path=None):
        plugin.write_text("import os\nMARKER = 'swapped-version'\n")
        return real_check(source, path or plugin)
    loader._check_module_safety = swap_then_check

    p = loader.load_plugin(plugin)
    assert p is not None
    assert p.process_audio.__globals__['MARKER'] == 'scanned-version'
