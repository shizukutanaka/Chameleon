"""Guards for the plugin-template hygiene fixes (2026-09-22).

- ``PluginManager.create_plugin_template`` used to default ``output_dir`` to
  ``"plugins"`` -- the live discovery directory -- so every generated stub
  was picked up by the next ``plugins list`` and presented as a real plugin.
- ``python plugin_system.py`` used to write ``demo_plugins/*.py`` and
  ``plugins/mycustomeffect_plugin.py`` into the caller's cwd (which is how
  that stub got committed), and its "Loaded plugins" list printed empty
  because generated code's ``from plugin_system import ...`` bound a second
  module copy under ``__main__``.
- The committed stub carried placeholder metadata ("Plugin Developer",
  "Description of MyCustomEffect plugin") as if it were a real plugin.
"""

import inspect
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SYSTEM = REPO_ROOT / "plugin_system.py"
COMMITTED_PLUGIN = REPO_ROOT / "plugins" / "mycustomeffect_plugin.py"


class TestTemplateOutputDir:
    def test_default_output_dir_is_not_a_discovery_directory(self):
        from plugin_system import PluginManager, PluginConfig
        default = inspect.signature(
            PluginManager.create_plugin_template).parameters[
            "output_dir"].default
        assert default not in PluginConfig().plugin_directories, (
            f"generated stubs land in '{default}', which discovery scans -- "
            "a placeholder template then presents as a real plugin")

    def test_generated_stub_lands_outside_live_scan(self, tmp_path, monkeypatch):
        from plugin_system import PluginManager, PluginConfig
        monkeypatch.chdir(tmp_path)
        manager = PluginManager(PluginConfig(
            plugin_directories=["plugins"], auto_discover=False))
        manager.initialize()
        path = manager.create_plugin_template("RoundCheck", "effect")
        assert Path(path).parent.name != "plugins"


class TestModuleDemoIsClean:
    """The __main__ demo must neither litter the caller's cwd nor fail to
    demonstrate what it prints."""

    @pytest.fixture
    def demo_run(self, tmp_path):
        proc = subprocess.run(
            [sys.executable, str(PLUGIN_SYSTEM)],
            cwd=tmp_path, capture_output=True, text=True, timeout=120)
        return proc, tmp_path

    def test_demo_leaves_no_files_behind(self, demo_run):
        proc, tmp_path = demo_run
        assert proc.returncode == 0, proc.stderr[-2000:]
        leftovers = [p for p in tmp_path.rglob("*") if p.is_file()]
        assert leftovers == [], (
            f"demo wrote files into the caller's cwd: {leftovers}")

    def test_demo_lists_loaded_plugins(self, demo_run):
        proc, _ = demo_run
        assert "\u2022 SimpleGain" in proc.stdout, (
            "generated plugins never loaded -- the __main__/plugin_system "
            "double-import broke issubclass again")

    def test_demo_template_goes_to_templates_not_live_dir(self, demo_run):
        proc, _ = demo_run
        assert "templates/" in proc.stdout and \
            "plugins/mycustomeffect_plugin.py" not in proc.stdout


class TestCommittedPluginHonesty:
    """The template generated into plugins/ got committed; until it is moved
    or deleted (needs user confirmation) it must describe itself honestly."""

    def test_no_placeholder_markers(self):
        src = COMMITTED_PLUGIN.read_text()
        assert "# TODO" not in src
        assert "Generated plugin template" not in src
        assert "Plugin Developer" not in src
        assert "Description of MyCustomEffect plugin" not in src

    def test_metadata_discloses_example_nature(self):
        import re
        src = COMMITTED_PLUGIN.read_text()
        desc = re.search(r'description="([^"]+)', src)
        assert desc is not None
        assert "example" in desc.group(1).lower() or \
            "template" in desc.group(1).lower(), (
            "plugins list presents this file as a real plugin -- its "
            "metadata must disclose it is the generated example")

    def test_docs_disclose_workers_constraint(self):
        en = (REPO_ROOT / "docs" / "en" / "commands.md").read_text()
        ja = (REPO_ROOT / "docs" / "ja" / "commands.md").read_text()
        assert "must be `1`" in en
        assert "`1`" in ja, "server --workers accepts only 1; both docs must say so"

    def test_ci_readme_lists_verified_phantoms(self):
        """Contract pin: ci/README's phantom inventory must keep covering
        every reference verified missing (all checked 2026-09-22)."""
        readme = (REPO_ROOT / "ci" / "README.md").read_text()
        for phantom in ("deployment_manager.py", "pytest-timeout",
                        "create backup", "create-release", "full"):
            assert phantom in readme, phantom
