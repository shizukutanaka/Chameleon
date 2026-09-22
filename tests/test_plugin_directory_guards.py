"""Plugin-directory creation must not mutate or crash on real dirs.

`_resolve_directory` and `PluginManager.initialize` create the configured
plugin directories on demand. Two verified escapes used to live there:
`os.chmod(0o750)` ran on every resolvable directory -- including
pre-existing ones a caller only asked to *list* -- and `mkdir` caught
only `PermissionError`, so an uncreatable path (ENOTDIR, EROFS, ENOSPC)
escaped as a raw traceback.
"""

import os
import stat
from pathlib import Path

import pytest

from plugin_system import PluginConfig, PluginLoader, PluginManager


def _loader(tmp_path):
    config = PluginConfig()
    config.plugin_directories = [str(tmp_path / "plugins")]
    return PluginLoader(config), config


def test_existing_directory_permissions_are_left_alone(tmp_path):
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir(mode=0o777)
    before = stat.S_IMODE(plugins_dir.stat().st_mode)

    loader, _ = _loader(tmp_path)
    resolved = loader._resolve_directory(str(plugins_dir))

    assert resolved == plugins_dir
    # Only a directory this call created may be chmod'ed; a pre-existing
    # one keeps whatever permissions the user gave it.
    assert stat.S_IMODE(plugins_dir.stat().st_mode) == before


@pytest.mark.skipif(os.name != "posix", reason="chmod semantics are POSIX")
def test_newly_created_directory_gets_secured(tmp_path):
    loader, _ = _loader(tmp_path)
    resolved = loader._resolve_directory(str(tmp_path / "plugins"))

    assert resolved is not None and resolved.exists()
    assert stat.S_IMODE(resolved.stat().st_mode) == 0o750


def test_uncreatable_directory_resolves_to_none(tmp_path):
    # A file blocks the path: `blocker/inside` can never be a directory,
    # so mkdir raises NotADirectoryError (OSError, not PermissionError).
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")

    loader, _ = _loader(tmp_path)
    resolved = loader._resolve_directory(str(blocker / "inside"))

    assert resolved is None


def test_initialize_skips_directories_it_cannot_create(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")

    config = PluginConfig()
    config.plugin_directories = [str(blocker / "inside"),
                                 str(tmp_path / "plugins")]
    manager = PluginManager(config)

    # Pre-fix this raised OSError out of initialize() -- a raw traceback
    # for a directory the caller supplied.
    manager.initialize()
    assert (tmp_path / "plugins").is_dir()
