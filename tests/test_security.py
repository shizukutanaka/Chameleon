"""Direct unit tests for SecurityValidator.

CHARTER §5 lists SecurityValidator as the mitigation for path-traversal and
resource-exhaustion threats. These tests verify those claims against the actual
implementation — not a hand-rolled re-implementation as validation_test.py did.

Each test group maps to a threat in §5 or a documented invariant in
security_validator.py.
"""

import os
import struct
import wave
from pathlib import Path

import pytest

from security_validator import SecurityConfig, SecurityValidator, SecurityError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validator(**kwargs) -> SecurityValidator:
    return SecurityValidator(SecurityConfig(**kwargs))


def _write_wav(path: Path, n_samples: int = 100) -> Path:
    """Write a minimal valid WAV so size-limit tests can use a real file."""
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(44100)
        f.writeframes(struct.pack("<" + "h" * n_samples, *([0] * n_samples)))
    return path


# ---------------------------------------------------------------------------
# Path-shape safety (traversal patterns, suspicious chars, length)
# ---------------------------------------------------------------------------

class TestPathShapeSafety:
    """Tests for the _is_path_shape_safe internal helper.

    Note: validate_path() calls Path.resolve() BEFORE _is_path_shape_safe, so
    traversal sequences like '../' are eliminated by the OS before the shape
    check runs. The defence against traversal in validate_path() therefore
    comes from _is_within_trusted_roots (see TestTrustedRoots), not from
    pattern matching. _is_path_shape_safe's job is to catch null bytes,
    suspicious shell-special characters, and over-long paths in the
    already-resolved string.
    """

    def _shape_safe(self, path_str: str) -> bool:
        return SecurityValidator()._is_path_shape_safe(path_str)

    @pytest.mark.parametrize("bad_path", [
        "/safe/dir/../etc/passwd",      # raw traversal (pre-resolve)
        "/safe/%2e%2e/passwd",          # URL-encoded traversal
        "/safe/dir/..%2f../etc",
        "/safe/dir/%2e%2e%2f../etc",
    ])
    def test_traversal_patterns_rejected_before_resolve(self, bad_path):
        assert self._shape_safe(bad_path) is False

    @pytest.mark.parametrize("bad_char", ["<", ">", "|", "\0", "*", "?"])
    def test_suspicious_characters_rejected(self, bad_char, tmp_path):
        bad_str = str(tmp_path) + f"/file{bad_char}name.wav"
        assert self._shape_safe(bad_str) is False

    def test_path_exceeding_max_length_rejected(self):
        long_path = "/" + "a" * 4097 + "/file.wav"
        assert self._shape_safe(long_path) is False

    def test_normal_path_accepted(self, tmp_path):
        p = _write_wav(tmp_path / "audio.wav")
        assert SecurityValidator.validate_path(str(p)) is True


# ---------------------------------------------------------------------------
# Trusted-root enforcement
# ---------------------------------------------------------------------------

class TestTrustedRoots:
    def test_path_inside_trusted_root_accepted(self, tmp_path):
        trusted = tmp_path / "trusted"
        trusted.mkdir()
        p = _write_wav(trusted / "song.wav")
        v = _validator(trusted_roots={str(trusted)})
        assert v.validate_path(str(p)) is True

    def test_path_outside_trusted_root_rejected(self, tmp_path):
        trusted = tmp_path / "trusted"
        trusted.mkdir()
        outside = tmp_path / "other"
        outside.mkdir()
        p = _write_wav(outside / "evil.wav")
        v = _validator(trusted_roots={str(trusted)})
        assert v.validate_path(str(p)) is False

    def test_prefix_collision_does_not_bypass_root(self, tmp_path):
        """'/safe/audio' as root must not allow '/safe/audio-exploit/'.

        _is_within_trusted_roots uses os.path.commonpath (component-wise), so a
        sibling directory whose name merely shares the root's string prefix is
        correctly rejected. Regression guard for the str.startswith bug
        (CHARTER §9).
        """
        trusted = tmp_path / "audio"
        trusted.mkdir()
        sibling = tmp_path / "audio-exploit"
        sibling.mkdir()
        p = _write_wav(sibling / "song.wav")
        v = _validator(trusted_roots={str(trusted)})
        assert v.validate_path(str(p)) is False

    def test_root_itself_and_nested_file_accepted(self, tmp_path):
        """A file genuinely nested under the root is still accepted after the
        commonpath hardening (guards against an over-strict fix)."""
        trusted = tmp_path / "audio"
        nested = trusted / "sub" / "deep"
        nested.mkdir(parents=True)
        p = _write_wav(nested / "song.wav")
        v = _validator(trusted_roots={str(trusted)})
        assert v.validate_path(str(p)) is True

    def test_empty_trusted_roots_allows_any_path(self, tmp_path):
        p = _write_wav(tmp_path / "song.wav")
        v = _validator(trusted_roots=set())
        assert v.validate_path(str(p)) is True


# ---------------------------------------------------------------------------
# Extension allowlist
# ---------------------------------------------------------------------------

class TestExtensionFilter:
    def test_allowed_extension_passes(self, tmp_path):
        p = _write_wav(tmp_path / "good.wav")
        v = _validator(allowed_extensions={".wav"})
        assert v.validate_path(str(p)) is True

    def test_disallowed_extension_rejected(self, tmp_path):
        p = tmp_path / "bad.exe"
        p.write_bytes(b"MZ")
        v = _validator(allowed_extensions={".wav"})
        assert v.validate_path(str(p)) is False

    def test_none_extensions_allows_any(self, tmp_path):
        p = _write_wav(tmp_path / "audio.wav")
        v = _validator(allowed_extensions=None)
        assert v.validate_path(str(p)) is True


# ---------------------------------------------------------------------------
# File-size limit (resource-exhaustion mitigation — CHARTER §5)
# ---------------------------------------------------------------------------

class TestFileSizeLimit:
    def test_file_within_limit_accepted(self, tmp_path):
        p = _write_wav(tmp_path / "small.wav")
        v = _validator(max_file_size=1024 * 1024)  # 1 MB
        assert v.validate_file_size(str(p)) is True

    def test_file_exceeding_limit_rejected(self, tmp_path):
        p = tmp_path / "big.bin"
        p.write_bytes(b"x" * 1024)  # 1 024 bytes
        v = _validator(max_file_size=512)  # 512-byte limit
        assert v.validate_file_size(str(p)) is False

    def test_nonexistent_file_returns_false(self, tmp_path):
        assert SecurityValidator.validate_file_size(str(tmp_path / "ghost.wav")) is False


# ---------------------------------------------------------------------------
# validate_path class-method vs instance behaviour
# ---------------------------------------------------------------------------

class TestHybridMethod:
    def test_class_level_call_does_not_raise(self, tmp_path):
        """Class-level usage (main.py style) must not raise."""
        p = _write_wav(tmp_path / "tone.wav")
        result = SecurityValidator.validate_path(str(p))
        assert isinstance(result, bool)

    def test_instance_level_call_matches_class_level(self, tmp_path):
        p = _write_wav(tmp_path / "tone.wav")
        cls_result = SecurityValidator.validate_path(str(p))
        inst_result = SecurityValidator().validate_path(str(p))
        assert cls_result == inst_result


# ---------------------------------------------------------------------------
# Raising-side variants: validate_file_path / validate_directory
# (validate_path returns bool; these raise SecurityError with a reason —
# the branches below were uncovered and are the messages callers surface)
# ---------------------------------------------------------------------------

class TestValidateFilePathRaises:
    def test_missing_file_for_read_raises(self, tmp_path):
        v = _validator()
        with pytest.raises(SecurityError, match="File not found"):
            v.validate_file_path(str(tmp_path / "missing.wav"), operation="read")

    def test_oversized_file_for_read_raises(self, tmp_path):
        p = tmp_path / "big.wav"
        p.write_bytes(b"x" * 1024)
        v = _validator(max_file_size=512)
        with pytest.raises(SecurityError, match="File too large"):
            v.validate_file_path(str(p), operation="read")

    def test_disallowed_extension_raises_with_reason(self, tmp_path):
        p = tmp_path / "script.exe"
        p.write_bytes(b"MZ")
        v = _validator(allowed_extensions={".wav"})
        with pytest.raises(SecurityError, match="Extension not allowed"):
            v.validate_file_path(str(p), operation="read")

    def test_write_to_new_file_returns_resolved_path(self, tmp_path):
        v = _validator()
        target = tmp_path / "new.wav"
        resolved = v.validate_file_path(str(target), operation="write")
        assert resolved == target.resolve()

    def test_suspicious_char_in_resolved_path_raises(self, tmp_path):
        # validate_file_path resolves first, so a raw ".." resolves away and is
        # caught by the roots check instead; the shape branch fires when the
        # RESOLVED path contains a suspicious character (e.g. '<').
        bad_dir = tmp_path / "bad<dir"
        bad_dir.mkdir()
        p = _write_wav(bad_dir / "x.wav")
        v = _validator()
        with pytest.raises(SecurityError, match="Unsafe file path"):
            v.validate_file_path(str(p), operation="read")


class TestValidateDirectory:
    def test_suspicious_char_in_resolved_path_raises(self, tmp_path):
        # Same resolve-first semantics as validate_file_path.
        v = _validator()
        with pytest.raises(SecurityError, match="Unsafe directory path"):
            v.validate_directory(str(tmp_path / "bad<dir"))

    def test_outside_trusted_roots_raises(self, tmp_path):
        trusted = tmp_path / "trusted"
        trusted.mkdir()
        v = _validator(trusted_roots={str(trusted)})
        with pytest.raises(SecurityError, match="outside trusted roots"):
            v.validate_directory(str(tmp_path / "other"))

    def test_existing_file_is_not_a_directory(self, tmp_path):
        p = _write_wav(tmp_path / "file.wav")
        v = _validator()
        with pytest.raises(SecurityError, match="Not a directory"):
            v.validate_directory(str(p))

    def test_missing_dir_with_require_exists_raises(self, tmp_path):
        v = _validator()
        with pytest.raises(SecurityError, match="does not exist"):
            v.validate_directory(str(tmp_path / "absent"), require_exists=True)

    def test_allow_create_creates_directory(self, tmp_path):
        v = _validator()
        target = tmp_path / "new" / "nested"
        resolved = v.validate_directory(str(target), allow_create=True)
        assert resolved.is_dir()


class TestSafeOpenFile:
    def test_unsafe_path_returns_none(self):
        v = _validator()
        assert v.safe_open_file("../escape.wav") is None

    def test_valid_file_returns_readable_handle(self, tmp_path):
        p = _write_wav(tmp_path / "tone.wav")
        v = _validator()
        handle = v.safe_open_file(str(p))
        try:
            assert handle is not None
            assert handle.read(4) == b"RIFF"
        finally:
            if handle:
                handle.close()

    def test_directory_path_returns_none(self, tmp_path):
        # A directory passes shape/extension checks but open() raises OSError.
        v = _validator(allowed_extensions=None)
        assert v.safe_open_file(str(tmp_path)) is None


class TestSanitizeFilename:
    def test_long_name_truncated_keeping_extension(self):
        name = "a" * 300 + ".wav"
        out = SecurityValidator.sanitize_filename(name)
        assert len(out) <= 255
        assert out.endswith(".wav")

    def test_dangerous_chars_replaced_with_underscores(self):
        assert SecurityValidator.sanitize_filename("///...") == "___..."
        assert SecurityValidator.sanitize_filename('<>:|?*') == "______"

    def test_empty_name_falls_back_to_untitled(self):
        assert SecurityValidator.sanitize_filename("") == "untitled"

    def test_dot_components_cannot_survive_sanitization(self):
        # '.' and '..' contain only legal characters but are not legal
        # components -- joined onto a directory they resolve to it or
        # its parent.
        assert SecurityValidator.sanitize_filename("..") == "untitled"
        assert SecurityValidator.sanitize_filename(".") == "untitled"
        # Names merely containing dots stay untouched.
        assert SecurityValidator.sanitize_filename("a..wav") == "a..wav"


class TestSecurityConfigFromEnvironment:
    def test_invalid_max_file_size_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("CHAMELEON_MAX_FILE_SIZE", "not-a-number")
        monkeypatch.delenv("CHAMELEON_TRUSTED_ROOTS", raising=False)
        monkeypatch.delenv("ALLOWED_DIRECTORIES", raising=False)
        cfg = SecurityConfig.from_environment()
        assert cfg.max_file_size > 0

    def test_valid_max_file_size_parsed(self, monkeypatch):
        monkeypatch.setenv("CHAMELEON_MAX_FILE_SIZE", "12345")
        cfg = SecurityConfig.from_environment()
        assert cfg.max_file_size == 12345

    def test_trusted_roots_env_parsed(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CHAMELEON_TRUSTED_ROOTS", str(tmp_path))
        cfg = SecurityConfig.from_environment()
        assert str(tmp_path) in cfg.trusted_roots

    def test_nonexistent_trusted_root_warns(self, monkeypatch, tmp_path):
        """A typo'd trusted root used to load silently -- every file would be
        rejected with no hint why. The entry stays (the dir may appear later
        -- a mount, a later mkdir) but the user must hear about it."""
        monkeypatch.setenv("CHAMELEON_TRUSTED_ROOTS", str(tmp_path / "ghost"))
        with pytest.warns(UserWarning, match="does not exist"):
            cfg = SecurityConfig.from_environment()
        assert str(tmp_path / "ghost") in cfg.trusted_roots
