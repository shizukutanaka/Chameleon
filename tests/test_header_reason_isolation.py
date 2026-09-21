"""A per-call out-parameter on a shared processor must not leak between
threads.

`WAVProcessor._header_rejection_reason` is set inside
`_read_wav_header_optimized` and read by the caller. `BatchProcessor`
runs one shared WAVProcessor across `--parallel` workers, so a plain
attribute lets thread B's reset overwrite the reason thread A is about
to report -- A's file then fails with the generic message (or worse,
B's). The field is now threading.local, same fix as
PerformanceTracker.start_time.
"""

import threading

from core import WAVProcessor


def test_rejection_reason_is_per_thread():
    proc = WAVProcessor()
    proc._header_rejection_reason = "main thread reason"

    def worker():
        proc._header_rejection_reason = "worker reason"
        assert proc._header_rejection_reason == "worker reason"

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    # With a shared attribute the worker's write overwrote ours.
    assert proc._header_rejection_reason == "main thread reason"


def test_real_read_records_specific_reason(tmp_path):
    proc = WAVProcessor()
    # RIFF header with format_tag=3 (IEEE float): valid container,
    # unsupported encoding -- the specific reason must be reported,
    # not the generic 'Invalid WAV file format'.
    bad_fmt = tmp_path / "float.wav"
    bad_fmt.write_bytes(
        b"RIFF" + (36).to_bytes(4, "little") + b"WAVE"
        + b"fmt " + (16).to_bytes(4, "little")
        + (3).to_bytes(2, "little") + (1).to_bytes(2, "little")
        + (44100).to_bytes(4, "little") + (88200).to_bytes(4, "little")
        + (2).to_bytes(2, "little") + (16).to_bytes(2, "little")
        + b"data" + (0).to_bytes(4, "little"))

    assert proc._read_wav_header_optimized(str(bad_fmt)) is None
    assert proc._header_rejection_reason is not None \
        and "format tag" in proc._header_rejection_reason
