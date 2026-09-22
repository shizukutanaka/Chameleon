"""Audit-76 regression tests.

1. ``api_server._enforce_rate_limit`` keeps one deque per identifier and only
   pruned windows that were literally empty -- but a deque is only trimmed on
   that identifier's *own* call. One-shot callers (a credential scan over many
   usernames) leave windows whose entries all expired yet are never removed:
   verified on the old code that 500 unique ids -> 501 retained windows after
   expiry. The cleanup must drop windows whose newest entry has expired.

2. ``spectral_utils._apply_band_gains`` computed bin width as
   ``sr / (2*(bins-1))`` which recovers the transform length N only for even
   N. For odd N every band boundary stretched by N/(N-1): at sr=44100,
   transform length 1103, bin 50 sits at 1999 Hz (mid band) but was labelled
   2000.9 Hz and given the *high* gain -- a 4.5x error on that component.
"""

import time

import pytest

from spectral_utils import _apply_band_gains


@pytest.fixture
def api():
    # api_server imports fastapi at module load -- skip in the stdlib-only
    # configuration while still running the spectral tests below.
    return pytest.importorskip("api_server")


def _spray_unique_identifiers(api_server, count: int) -> None:
    for i in range(count):
        api_server._enforce_rate_limit(f"login:10.{i % 256}.{i // 256}.1:user{i}")


def test_rate_limiter_drops_fully_expired_windows(api) -> None:
    api.api_state._rate_limit_windows.clear()
    try:
        _spray_unique_identifiers(api, 500)
        assert len(api.api_state._rate_limit_windows) > 200

        # Age every entry past the 60 s window without removing the deques.
        window_seconds = api.SECURITY_CONFIG["rate_limit_window_seconds"]
        for w in api.api_state._rate_limit_windows.values():
            while w:
                w.popleft()
            w.append(time.time() - window_seconds - 1)

        api._enforce_rate_limit("login:127.0.0.1:trigger")
        assert len(api.api_state._rate_limit_windows) == 1
    finally:
        api.api_state._rate_limit_windows.clear()


def test_rate_limiter_keeps_live_windows(api) -> None:
    api.api_state._rate_limit_windows.clear()
    try:
        _spray_unique_identifiers(api, 500)
        # One identifier stays fresh: its window must survive the cleanup.
        for w in api.api_state._rate_limit_windows.values():
            while w:
                w.popleft()
            w.append(time.time() - 120)
        api._enforce_rate_limit("login:127.0.0.1:fresh")

        windows = api.api_state._rate_limit_windows
        assert set(windows) == {"login:127.0.0.1:fresh"}
        assert len(windows["login:127.0.0.1:fresh"]) == 1
    finally:
        api.api_state._rate_limit_windows.clear()


def test_band_gain_uses_true_transform_length_on_odd_n() -> None:
    # N=1103 (odd), sr=44100: bin 50 is at 1999.1 Hz -> mid band (< 2000 Hz).
    # The old 2*(bins-1) formula labelled it 2000.9 Hz and applied high_gain.
    n, sr = 1103, 44100
    spectrum = [0j] * (n // 2 + 1)
    spectrum[50] = 1 + 0j
    out = _apply_band_gains(spectrum, sr, n,
                            low_gain=1.0, mid_gain=2.0, high_gain=9.0)
    assert abs(out[50]) == pytest.approx(2.0)


def test_band_gain_even_n_unchanged() -> None:
    # Contract pin: even-length transforms keep the exact same boundary
    # arithmetic as before (sr/N == sr/(2*(bins-1)) when N is even).
    n, sr = 4096, 44100
    spectrum = [0j] * (n // 2 + 1)
    spectrum[50] = 1 + 0j  # 50 * 44100/4096 = 538 Hz -> mid
    spectrum[186] = 1 + 0j  # 2002 Hz -> high
    out = _apply_band_gains(spectrum, sr, n,
                            low_gain=1.0, mid_gain=2.0, high_gain=9.0)
    assert abs(out[50]) == pytest.approx(2.0)
    assert abs(out[186]) == pytest.approx(9.0)
