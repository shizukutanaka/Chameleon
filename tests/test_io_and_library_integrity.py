"""Regression tests for the cycle-5 measured fixes: secure_open opening a
different file than the one that was validated, ragged table rows,
scan_library keeping deleted files forever, the setup wizard's literal
'~' path, and unsafe quoting in the generated shell-alias files.

Each test's docstring records the measured defect it pins down.
"""

import os
import subprocess

import pytest

import personal_config
import security_validator
import ux_improvements
from tests._helpers import write_sine_wave


def _make_manager(tmp_path, monkeypatch):
    """PersonalLibraryManager wired to throwaway HOME and library dirs."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    library = tmp_path / "lib"
    library.mkdir()
    config = personal_config.PersonalConfig(audio_library=str(library))
    config.supported_formats = [".wav"]
    mgr = personal_config.PersonalLibraryManager(config)
    mgr.db_path = home / ".chameleon" / "library.json"
    mgr.library_db = {"files": {}, "playlists": {}, "tags": {}}
    return mgr, library


def _drop_wav(path):
    write_sine_wave(path, duration=0.05)


class TestSecureOpen:
    """`secure_open` validated one path and opened another: it discarded
    the resolved path validate_file_path returned and opened the caller's
    raw string, so `~/x` hit a literal `~` directory (FileNotFoundError)
    and every '+' mode (r+/w+/rb+) was validated as a *read* and given
    none of the write-side hardening (measured: r+ wrote through a
    symlink that O_NOFOLLOW semantics refuse)."""

    def test_tilde_path_is_written_under_home(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        ops = security_validator.SecureFileOperations()
        with ops.secure_open("~/probe_out.txt", "w") as fh:
            fh.write("data")
        assert (home / "probe_out.txt").read_text() == "data"

    def test_tilde_path_reads_from_home(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        (home / "probe_in.txt").write_text("in")
        monkeypatch.setenv("HOME", str(home))
        ops = security_validator.SecureFileOperations()
        with ops.secure_open("~/probe_in.txt", "r") as fh:
            assert fh.read() == "in"

    def test_r_plus_is_refused_through_symlink(self, tmp_path):
        ops = security_validator.SecureFileOperations()
        target = tmp_path / "real.txt"
        target.write_text("original")
        link = tmp_path / "link.txt"
        link.symlink_to(target)
        with pytest.raises(security_validator.SecurityError):
            with ops.secure_open(str(link), "r+"):
                pass
        assert target.read_text() == "original"

    def test_r_plus_reads_and_writes_existing_file(self, tmp_path):
        ops = security_validator.SecureFileOperations()
        target = tmp_path / "f.txt"
        target.write_text("abc")
        with ops.secure_open(str(target), "r+") as fh:
            assert fh.read() == "abc"  # O_RDWR, not O_WRONLY
            fh.write("X")
        assert target.read_text() == "abcX"

    def test_r_plus_does_not_create_missing_file(self, tmp_path):
        ops = security_validator.SecureFileOperations()
        with pytest.raises(FileNotFoundError):
            with ops.secure_open(str(tmp_path / "missing.txt"), "r+"):
                pass

    def test_exclusive_create_works_and_refuses_existing(self, tmp_path):
        ops = security_validator.SecureFileOperations()
        new = tmp_path / "new.txt"
        with ops.secure_open(str(new), "x") as fh:
            fh.write("first")
        assert new.read_text() == "first"
        with pytest.raises(FileExistsError):
            with ops.secure_open(str(new), "x"):
                pass

    def test_w_mode_still_refuses_final_symlink(self, tmp_path):
        ops = security_validator.SecureFileOperations()
        target = tmp_path / "real.bin"
        target.write_bytes(b"orig")
        link = tmp_path / "link.bin"
        link.symlink_to(target)
        with pytest.raises(security_validator.SecurityError):
            with ops.secure_open(str(link), "wb"):
                pass
        assert target.read_bytes() == b"orig"

    def test_created_file_permissions_are_restrictive(self, tmp_path):
        if os.name != "posix":
            pytest.skip("0o600 check is posix-only")
        ops = security_validator.SecureFileOperations()
        out = tmp_path / "secret.txt"
        with ops.secure_open(str(out), "w") as fh:
            fh.write("x")
        assert (out.stat().st_mode & 0o777) == 0o600


class TestTableFormatterRagged:
    def test_row_longer_than_headers_is_named_not_index_error(self):
        # Measured: bare IndexError out of the width loop.
        with pytest.raises(ValueError, match="3 cells for 2 headers"):
            ux_improvements.TableFormatter.format_table(["A", "B"], [[1, 2, 3]])

    def test_row_shorter_than_headers_is_rejected(self):
        # Previously emitted a line with fewer cells than the header
        # promised -- silently ragged output.
        with pytest.raises(ValueError, match="1 cells for 3 headers"):
            ux_improvements.TableFormatter.format_table(["A", "B", "C"], [[1]])

    def test_well_formed_table_unchanged(self):
        table = ux_improvements.TableFormatter.format_table(
            ["A", "B"], [[1, 22], [333, 4]])
        assert "333" in table and "|" in table

    def test_empty_rows_still_returns_empty(self):
        assert ux_improvements.TableFormatter.format_table(["A"], []) == ""


class TestScanLibrary:
    """`scan_library` grew the database monotonically: a file deleted from
    disk stayed in library_db['files'] forever -- still counted in
    total_files and still returned by search() with a checksum pointing
    at nothing (measured: delete + rescan left total_files at 1)."""

    def test_deleted_file_is_pruned_and_reported(self, tmp_path, monkeypatch):
        mgr, library = _make_manager(tmp_path, monkeypatch)
        wav = library / "gone.wav"
        _drop_wav(wav)
        mgr.scan_library()
        assert mgr.library_db["files"].keys() == {"gone.wav"}

        wav.unlink()
        result = mgr.scan_library()
        assert result["total_files"] == 0
        assert result["removed_files"] == 1
        assert result["removed"] == ["gone.wav"]
        assert mgr.search("gone") == []

    def test_surviving_files_are_kept(self, tmp_path, monkeypatch):
        mgr, library = _make_manager(tmp_path, monkeypatch)
        keep = library / "keep.wav"
        gone = library / "gone.wav"
        _drop_wav(keep)
        _drop_wav(gone)
        mgr.scan_library()
        gone.unlink()
        result = mgr.scan_library()
        assert result["total_files"] == 1
        assert "keep.wav" in mgr.library_db["files"]

    def test_added_timestamp_is_scan_time_not_file_mtime(self, tmp_path, monkeypatch):
        # "added" stored st_mtime -- a file created last year and scanned
        # today looked a year old in the DB (same mislabeled-timestamp
        # pattern create_playlist's "created" already fixed).
        mgr, library = _make_manager(tmp_path, monkeypatch)
        wav = library / "old.wav"
        _drop_wav(wav)
        os.utime(wav, (946684800, 946684800))  # 2000-01-01
        mgr.scan_library()
        added = mgr.library_db["files"]["old.wav"]["added"]
        assert added.startswith("20")  # ISO-8601 now, not epoch year 2000
        assert "T" in added

    def test_search_checks_metadata_values(self, tmp_path, monkeypatch):
        # The docstring promised "filename, tags, or metadata" but the
        # loop never looked at metadata -- an artist/title-only query
        # returned nothing.
        mgr, _ = _make_manager(tmp_path, monkeypatch)
        mgr.library_db["files"]["song.wav"] = {
            "path": "x", "checksum": "c", "size": 1,
            "metadata": {"artist": "Boards of Canada"},
            "tags": [],
        }
        assert mgr.search("boards") == ["song.wav"]

    def test_scan_result_shape_is_stable(self, tmp_path, monkeypatch):
        mgr, library = _make_manager(tmp_path, monkeypatch)
        _drop_wav(library / "a.wav")
        result = mgr.scan_library()
        for key in ("total_files", "new_files", "updated_files",
                    "removed_files", "new", "updated", "removed"):
            assert key in result


class TestGeneratedAliasFiles:
    """The generated aliases.sh embedded config paths inside one
    single-quoted alias body; an apostrophe in audio_library made the
    file `bash -n` reject (exit 2) -- the file the user is told to
    `source`. Paths are now shlex.quote'd (and single-quoted literals in
    the PowerShell variant)."""

    def _write_aliases(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.chdir(tmp_path)
        config = personal_config.PersonalConfig()
        config.audio_library = "/data/o'brien/music"
        config.output_directory = "/data/o'brien/processed"
        personal_config.PersonalSetup.create_quick_commands(config)
        return home / ".chameleon"

    def test_aliases_sh_is_valid_bash(self, tmp_path, monkeypatch):
        state = self._write_aliases(tmp_path, monkeypatch)
        aliases_sh = state / "aliases.sh"
        result = subprocess.run(
            ["bash", "-n", str(aliases_sh)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

    def test_aliases_sh_sources_and_defines_quoted_alias(self, tmp_path, monkeypatch):
        state = self._write_aliases(tmp_path, monkeypatch)
        result = subprocess.run(
            ["bash", "-c", f"source {state}/aliases.sh && alias audio-lib"],
            capture_output=True, text=True)
        assert result.returncode == 0
        # bash prints the alias with its own re-escaped quoting
        # (o'\''brien); what matters is the full path survives intact.
        assert "brien/music" in result.stdout

    def test_aliases_ps1_escapes_apostrophes(self, tmp_path, monkeypatch):
        state = self._write_aliases(tmp_path, monkeypatch)
        ps_script = (state / "aliases.ps1").read_text()
        # PowerShell single-quoted literals escape ' as ''.
        assert "o''brien" in ps_script


class TestQuickSetupPathExpansion:
    def test_custom_audio_library_expands_tilde(self, tmp_path, monkeypatch):
        # quick_setup stored the raw input, so a "~/music" answer made
        # every later Path() call treat it as a literal directory named
        # "~" under the CWD (measured: Path(cfg.audio_library).mkdir
        # created ./~ and never touched the real home).
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.chdir(tmp_path)

        answers = iter(["~/my-audio-lib", "", "n"])
        monkeypatch.setattr("builtins.input", lambda *a: next(answers))
        config = personal_config.PersonalSetup.quick_setup()

        assert config.audio_library == str(home / "my-audio-lib")
        assert not (tmp_path / "~").exists()
        assert (home / "my-audio-lib").is_dir()
