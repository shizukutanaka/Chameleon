"""StateRecoveryManager must not touch the filesystem at construction.

``BatchProcessor`` is a module-level singleton, so an ``__init__`` that ran
``state_dir.mkdir`` made every ``import core`` -- every CLI invocation,
including ``--help`` -- create ``~/.chameleon_state``, a filesystem write
the user never asked for. The directory is now created lazily on the first
``record_state()`` call.
"""

import core


def test_state_manager_does_not_write_to_fs_on_init(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("CHAMELEON_STATE_DIR", raising=False)

    mgr = core.StateRecoveryManager()

    assert mgr.state_dir == tmp_path / ".chameleon_state"
    assert not mgr.state_dir.exists()


def test_state_manager_creates_dir_on_first_record(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("CHAMELEON_STATE_DIR", raising=False)

    mgr = core.StateRecoveryManager()
    out = mgr.record_state({"files": 1})

    assert out is not None and out.exists()
    assert mgr.state_dir.is_dir()
