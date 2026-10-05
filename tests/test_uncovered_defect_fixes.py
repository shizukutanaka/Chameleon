"""Regression tests for the four defects left uncovered by the closed
audit PR batch (#299, #300, #329, #332).

Each test pins one contract:
- validate_path rejects existing non-regular files (FIFOs/sockets/dirs)
- mono downmix rounds the channel average instead of truncating
- login rate limiting also applies per-IP, not only per-(IP, username)
- the CLI output-path resolver refuses destinations that are the input
"""

import os
import struct
import wave
from pathlib import Path

import pytest

import core
from core import SecurityValidator


def _write_stereo_wav(path: Path, frames):
    """frames: iterable of (left, right) 16-bit sample pairs."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"".join(
            struct.pack("<hh", l, r) for l, r in frames))


def _read_mono_samples(path: Path):
    with wave.open(str(path)) as w:
        raw = w.readframes(w.getnframes())
        return struct.unpack(f"<{len(raw) // 2}h", raw)


class TestValidatePathNonRegularFile:
    def test_fifo_rejected(self, tmp_path):
        fifo = tmp_path / "in.wav"
        os.mkfifo(fifo)
        assert not SecurityValidator.validate_path(str(fifo))

    def test_directory_rejected(self, tmp_path):
        # A directory is not a file path — previously returned True.
        assert not SecurityValidator.validate_path(str(tmp_path))

    def test_socket_rejected(self):
        import socket as s
        import tempfile
        # AF_UNIX path limit (~104 chars) forbids tmp_path on macOS.
        sock_path = tempfile.mktemp(dir="/tmp", suffix=".wav")
        srv = s.socket(s.AF_UNIX, s.SOCK_STREAM)
        try:
            srv.bind(sock_path)
            assert not SecurityValidator.validate_path(sock_path)
        finally:
            srv.close()

    def test_regular_file_still_accepted(self, tmp_path):
        f = tmp_path / "ok.wav"
        f.write_bytes(b"RIFF")
        assert SecurityValidator.validate_path(str(f))

    def test_missing_path_still_accepted(self, tmp_path):
        # Output paths that don't exist yet must not be rejected.
        assert SecurityValidator.validate_path(str(tmp_path / "out.wav"))


class TestMonoDownmixRounding:
    def test_half_integer_average_rounds_not_truncates(self, tmp_path):
        src = tmp_path / "stereo.wav"
        dst = tmp_path / "mono.wav"
        # (1, 2) -> avg 1.5: int() gave 1 (toward zero), round gives 2.
        # (-1, -2) -> avg -1.5: int() gave -1, round gives -2.
        _write_stereo_wav(src, [(1, 2), (-1, -2), (10, 10)])
        result = core.to_mono(str(src), str(dst))
        assert result.success, result.message
        assert _read_mono_samples(dst) == (2, -2, 10)


class TestCliOutputSameAsInput:
    def test_explicit_output_equal_input_rejected(self, tmp_path):
        src = tmp_path / "song.wav"
        src.write_bytes(b"RIFF")
        from main import AudioProcessor as CliProcessor
        proc = CliProcessor()
        with pytest.raises(ValueError, match="same file|in-place"):
            proc._resolve_output_path(
                str(src), suffix="_norm.wav",
                explicit_path=str(src), output_dir=None)

    def test_symlinked_explicit_output_rejected(self, tmp_path):
        src = tmp_path / "song.wav"
        src.write_bytes(b"RIFF")
        link = tmp_path / "alias.wav"
        link.symlink_to(src)
        from main import AudioProcessor as CliProcessor
        proc = CliProcessor()
        with pytest.raises(ValueError, match="same file|in-place"):
            proc._resolve_output_path(
                str(src), suffix="_norm.wav",
                explicit_path=str(link), output_dir=None)


class TestPersistUploadSecureOpenRefusal:
    def test_oserror_from_secure_open_is_400_not_500(self, tmp_path, monkeypatch):
        """A symlink swapped in between validate_file_path's resolution and
        secure_open's O_NOFOLLOW open surfaces as OSError; _persist_upload
        must map that refusal to 400, not the generic 500."""
        pytest.importorskip("fastapi")
        import asyncio
        import api_server
        from fastapi import HTTPException

        real_open = os.open

        def _race_open(path, flags, mode=0o777, *args, **kwargs):
            if str(path).endswith("race.wav"):
                raise OSError(62, "Too many levels of symbolic links")
            return real_open(path, flags, mode, *args, **kwargs)

        monkeypatch.setattr(os, "open", _race_open)

        class _EmptyUpload:
            async def read(self, n):
                return b""
            async def close(self):
                pass

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(api_server._persist_upload(
                _EmptyUpload(), tmp_path / "race.wav"))
        assert exc_info.value.status_code == 400


class TestLoginRateLimitPerIp:
    def test_username_rotation_shares_ip_window(self, monkeypatch):
        """Rotating usernames from one IP must exhaust a shared window."""
        pytest.importorskip("fastapi")
        pytest.importorskip("httpx")
        import api_server
        from fastapi.testclient import TestClient

        monkeypatch.setitem(api_server.SECURITY_CONFIG,
                            "enable_rate_limiting", True)
        monkeypatch.setitem(api_server.SECURITY_CONFIG,
                            "rate_limit_max_requests", 2)
        monkeypatch.setitem(api_server.SECURITY_CONFIG,
                            "rate_limit_window_seconds", 60)
        api_server.api_state._rate_limit_windows.clear()

        client = TestClient(api_server.app, base_url="http://localhost")

        def login(user):
            return client.post("/auth/login", json={
                "username": user,
                "password": "irrelevant",
                "clearance_level": "UNCLASSIFIED",
            })

        assert login("rotation-user-a").status_code == 200
        assert login("rotation-user-b").status_code == 200
        # Third attempt from the same IP with a *fresh* username would have
        # passed under the per-(IP, username) key alone.
        assert login("rotation-user-c").status_code == 429
