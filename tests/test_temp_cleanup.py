"""RecoveryManager._cleanup_temp_files must never follow symlinks.

The cleanup runs inside a shared temp directory (``tempfile.gettempdir()`` —
world-writable ``/tmp`` on multi-user systems) when a batch operation retries
after a disk-space OSError. A ``chameleon_*`` symlink planted there pointed at
a victim directory made the cleanup unlink the *target's* files. Deletion must
stop at the link.
"""

import core


def _sandbox(tmp_path, monkeypatch):
    sandbox = tmp_path / "tmp"
    sandbox.mkdir()
    monkeypatch.setattr(core.tempfile, "gettempdir", lambda: str(sandbox))
    return sandbox


def test_chameleon_symlink_to_directory_deletes_only_the_link(tmp_path, monkeypatch):
    sandbox = _sandbox(tmp_path, monkeypatch)
    victim = sandbox / "victim"
    victim.mkdir()
    (victim / "important.txt").write_text("keep me")
    (victim / "nested").mkdir()
    (victim / "nested" / "deep.txt").write_text("keep me too")

    (sandbox / "chameleon_evil").symlink_to(victim)
    (sandbox / "chameleon_legit.tmp").write_text("junk")

    core.RecoveryManager()._cleanup_temp_files()

    assert (victim / "important.txt").exists()
    assert (victim / "nested" / "deep.txt").exists()
    assert not (sandbox / "chameleon_evil").exists()  # the link itself goes
    assert not (sandbox / "chameleon_legit.tmp").exists()


def test_symlinked_child_inside_a_real_temp_dir_is_not_followed(tmp_path, monkeypatch):
    sandbox = _sandbox(tmp_path, monkeypatch)
    victim = sandbox / "victim"
    victim.mkdir()
    (victim / "important.txt").write_text("keep me")

    real_dir = sandbox / "chameleon_cache"
    real_dir.mkdir()
    (real_dir / "data.bin").write_bytes(b"\x00")
    (real_dir / "inner_link").symlink_to(victim)

    core.RecoveryManager()._cleanup_temp_files()

    assert (victim / "important.txt").exists()
    assert not real_dir.exists()
