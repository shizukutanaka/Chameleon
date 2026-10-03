"""Tests for the plugin sandbox security checks."""

import threading
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


@pytest.mark.parametrize("prim", ["attrgetter", "itemgetter", "methodcaller"])
def test_check_module_safety_rejects_opaque_name_primitives(tmp_path, prim):
    """operator.attrgetter("__class__.__subclasses__") reaches every
    attribute the deny list names -- through a string the audit cannot
    read. Verified end to end: the chain reached os.system."""
    loader = PluginLoader(PluginConfig())
    bad = tmp_path / f"bypass_{prim}.py"
    bad.write_text(f"import operator\nag = operator.{prim}\n")

    with pytest.raises(SecurityError, match="Unsafe attribute access"):
        loader._check_module_safety(Path(bad))


def test_check_module_safety_rejects_aliased_dangerous_from_import(tmp_path):
    """`from operator import attrgetter as ag` re-binds a denied name to a
    fresh identifier the walk cannot see; the imported name itself must be
    checked, not just the alias (verified: this form reached os.system)."""
    loader = PluginLoader(PluginConfig())
    bad = tmp_path / "bypass_alias.py"
    bad.write_text("from operator import attrgetter as ag\n")

    with pytest.raises(SecurityError, match="Unsafe import"):
        loader._check_module_safety(Path(bad))


def test_check_module_safety_rejects_star_import(tmp_path):
    """`from operator import *` binds attrgetter and friends invisibly --
    no imported name appears anywhere for the walk to check."""
    loader = PluginLoader(PluginConfig())
    bad = tmp_path / "bypass_star.py"
    bad.write_text("from operator import *\n")

    with pytest.raises(SecurityError, match="Unsafe import"):
        loader._check_module_safety(Path(bad))


@pytest.mark.parametrize("ctor", ["FunctionType", "CodeType", "MethodType"])
def test_check_module_safety_rejects_types_code_ctors(tmp_path, ctor):
    """types.FunctionType/CodeType/MethodType are code-execution
    constructors reachable without compile(): a crafted CodeType ran
    arbitrary bytecode (verified end to end)."""
    loader = PluginLoader(PluginConfig())
    bad = tmp_path / f"bypass_{ctor}.py"
    bad.write_text(f"import types\nf = types.{ctor}\n")

    with pytest.raises(SecurityError, match="Unsafe attribute access"):
        loader._check_module_safety(Path(bad))


def test_check_module_safety_rejects_traceback_import(tmp_path):
    """traceback.walk_stack hands out live host frames; f_globals was then
    reachable via getattr with a literal name the old six-name subset did
    not cover (verified: a probe plugin ran exec this way)."""
    loader = PluginLoader(PluginConfig())
    bad = tmp_path / "bypass_tb.py"
    bad.write_text("import traceback\n")

    with pytest.raises(SecurityError, match="Unsafe import"):
        loader._check_module_safety(Path(bad))


def test_check_module_safety_rejects_getattr_literal_danger_names(tmp_path):
    """getattr(obj, "f_globals") faces the same deny list as attribute
    access -- the previous six-name literal subset let frame names
    through."""
    loader = PluginLoader(PluginConfig())
    bad = tmp_path / "bypass_getattr_lit.py"
    bad.write_text('g = getattr(x, "f_globals")\n')

    with pytest.raises(SecurityError, match="Unsafe getattr"):
        loader._check_module_safety(Path(bad))



def test_execute_with_limits_runs_off_main_thread():
    """SIGALRM delivery exists only in the main thread -- on any other
    thread signal.signal() raised ValueError before the plugin callable
    ever ran (verified: a worker-thread call crashed with ValueError, not
    the function result). Off-main-thread callers now take the
    thread-join fallback."""
    sandbox = PluginSandbox(PluginConfig())
    result = []

    def run():
        result.append(sandbox.execute_with_limits(lambda: 42))

    worker = threading.Thread(target=run)
    worker.start()
    worker.join(10)

    assert result == [42]


def test_execute_with_limits_times_out_off_main_thread():
    """The thread-join fallback must still enforce the timeout for
    off-main-thread callers."""
    import time
    sandbox = PluginSandbox(PluginConfig(max_execution_time=1))
    result = []

    def run():
        try:
            sandbox.execute_with_limits(lambda: time.sleep(30))
            result.append("no timeout")
        except TimeoutError:
            result.append("timeout")

    worker = threading.Thread(target=run)
    worker.start()
    worker.join(10)

    assert result == ["timeout"]
<<<<<<< HEAD


class _PosixRlimit:
    """resource stand-in with POSIX semantics: an unprivileged process may
    lower the hard limit but can never raise it again."""

    RLIMIT_AS = 9
    RLIM_INFINITY = -1

    class error(Exception):
        pass

    def __init__(self, soft, hard):
        self.soft = soft
        self.hard = hard

    def getrlimit(self, which):
        assert which == self.RLIMIT_AS
        return (self.soft, self.hard)

    def setrlimit(self, which, limits):
        assert which == self.RLIMIT_AS
        soft_req, hard_req = limits
        finite_hard = self.hard != self.RLIM_INFINITY
        raises_hard = hard_req == self.RLIM_INFINITY or (
            finite_hard and hard_req > self.hard)
        if raises_hard:
            raise self.error("cannot raise hard limit without privilege")
        self.soft, self.hard = limits


def test_apply_memory_limit_restores_process_limits(monkeypatch):
    """setrlimit used to write (target, target), lowering the *hard* limit;
    unprivileged restore then failed EPERM and the whole process -- host
    included -- stayed capped at max_memory_mb after every sandboxed call.
    Only the soft limit is now lowered, so the restore is always legal."""
    import plugin_system

    state = _PosixRlimit(soft=4 << 30, hard=8 << 30)
    monkeypatch.setattr(plugin_system, "resource", state)

    sandbox = PluginSandbox(PluginConfig(max_memory_mb=64))
    with sandbox._apply_memory_limit():
        pass

    assert (state.soft, state.hard) == (4 << 30, 8 << 30)


def test_execute_with_limits_restores_memory_off_main_thread(monkeypatch):
    """The review's exact scenario: an off-main-thread call enters the
    thread-join fallback, whose _apply_memory_limit used to leave the
    process hard-capped even though the plugin call succeeded."""
    import plugin_system

    state = _PosixRlimit(soft=4 << 30, hard=8 << 30)
    monkeypatch.setattr(plugin_system, "resource", state)

    sandbox = PluginSandbox(PluginConfig(max_memory_mb=64))
    result = []

    def run():
        result.append(sandbox.execute_with_limits(lambda: 42))

    worker = threading.Thread(target=run)
    worker.start()
    worker.join(10)

    assert result == [42]
    assert (state.soft, state.hard) == (4 << 30, 8 << 30)
||||||| 7bcfad6
=======

>>>>>>> origin/main
