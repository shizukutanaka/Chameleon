"""create_plugin_template input contract.

plugin_name is interpolated into the output filename AND the generated
class declaration. Before validation, "../x" escaped output_dir and
"bad-name!" emitted a plugin file that could never compile. Unknown
categories silently generated a utility plugin.
"""

from pathlib import Path

import pytest

import plugin_system


@pytest.fixture()
def manager():
    return plugin_system.PluginManager()


def test_template_rejects_non_identifier_names(tmp_path, manager):
    for bad in ("../../escape", "bad-name!", "2bad", "my name", "", 5):
        with pytest.raises(ValueError):
            manager.create_plugin_template(bad, "effect", str(tmp_path))
    # Nothing may have been written outside (or inside) the target dir.
    assert list(tmp_path.iterdir()) == []


def test_template_rejects_unknown_category(tmp_path, manager):
    with pytest.raises(ValueError):
        manager.create_plugin_template("my_plugin", "bogus", str(tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_template_generates_compilable_plugin(tmp_path, manager):
    out = manager.create_plugin_template("my_gain", "effect", str(tmp_path))
    path = Path(out)
    assert path.parent == tmp_path
    compile(path.read_text(), out, "exec")  # raises SyntaxError if invalid
