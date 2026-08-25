"""Where the file inspector looks for injected code, and why it matters.

`DeepFileInspector._scan_for_suspicious_content` searched the entire file --
up to 10 MB, PCM payload included -- for every entry in one flat list of
patterns. Two of those entries are two bytes long (`MZ`, `#!`), so in 16-bit
audio each has about a 1-in-65,536 chance at every offset. That is not a rare
event in a recording; it is a near-certainty. Measured before the change, on
ordinary content:

    1 second of a 440 Hz sine      Suspicious pattern: #!
    10 seconds of a 440 Hz sine    Suspicious pattern: #!
    10 seconds of white noise      Suspicious pattern: #!

A security check that fires on almost everything is worse than no check. It
does not merely waste attention -- it hides the real hit, which arrives looking
exactly like the thousand false ones before it, and it teaches the user that
this project's validation layer is noise. That layer is what `CHARTER.md` §1
offers as the reason to trust the tool.

The fix was not to loosen the check but to aim it. The patterns were never
interchangeable:

* `MZ`, `\\x7fELF` and `#!` make a file executable, and only at offset 0.
* Markup and code fragments matter in the container's text regions, where
  another tool may read them -- never in `data`, which is sample values.

So the scan is now strictly more informative than it was: it reports fewer
things, and every one of them means something.
"""

import struct
import wave
from pathlib import Path

import pytest

from advanced_validation import DeepFileInspector


SAMPLE_RATE = 44100


@pytest.fixture
def inspector():
    return DeepFileInspector()


def _write_wav(path, frames):
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(frames)
    return Path(path)


def _tone_frames(seconds=1.0, freq=440.0):
    import math
    count = int(SAMPLE_RATE * seconds)
    return b"".join(
        struct.pack("<h", int(0.5 * 32767 * math.sin(2 * math.pi * freq * i / SAMPLE_RATE)))
        for i in range(count)
    )


def _warnings(inspector, path):
    return [w for w in inspector.inspect_file(path).warnings if "Suspicious pattern" in w]


# --- ordinary audio is not suspicious ------------------------------------

@pytest.mark.parametrize("freq", [100.0, 440.0, 1000.0])
def test_a_plain_tone_raises_no_suspicion(inspector, tmp_path, freq):
    wav = _write_wav(tmp_path / f"tone{freq}.wav", _tone_frames(freq=freq))

    assert _warnings(inspector, wav) == []


def test_a_tone_long_enough_to_hit_every_two_byte_pattern_is_still_clean(inspector, tmp_path):
    # Ten seconds is 882,000 samples: `#!` and `MZ` are each near-certain to
    # occur somewhere in the payload by chance. That is exactly the case the
    # old whole-file scan flagged.
    wav = _write_wav(tmp_path / "long.wav", _tone_frames(seconds=10.0))

    assert _warnings(inspector, wav) == []


def test_bytes_that_spell_code_inside_the_data_chunk_are_just_audio(inspector, tmp_path):
    payload = b"MZ\x7fELF#!<?php <script import os; eval( exec( system( <html"
    if len(payload) % 2:
        payload += b"\x00"
    wav = _write_wav(tmp_path / "payload.wav", b"\x00\x00" * 50 + payload + b"\x00\x00" * 50)

    result = inspector.inspect_file(wav)
    assert result.is_valid
    assert _warnings(inspector, wav) == []


# --- real threats are still caught ---------------------------------------

@pytest.mark.parametrize("signature,label", [
    (b"#!/bin/sh\necho hello\n", "shell script"),
    (b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 100, "ELF binary"),
    (b"MZ\x90\x00\x03" + b"\x00" * 100, "DOS/Windows executable"),
])
def test_an_executable_signature_at_offset_zero_is_reported(inspector, tmp_path, signature, label):
    disguised = tmp_path / "not-really.wav"
    disguised.write_bytes(signature)

    assert _warnings(inspector, disguised), f"{label} was not reported"


def test_a_disguised_executable_is_also_an_outright_error(inspector, tmp_path):
    # The warning is the secondary signal; failing the magic-number check is
    # the one that stops it being processed.
    disguised = tmp_path / "not-really.wav"
    disguised.write_bytes(b"#!/bin/sh\necho hello\n")

    result = inspector.inspect_file(disguised)
    assert not result.is_valid
    assert any("Invalid file type" in e for e in result.errors)


def test_markup_injected_into_a_metadata_chunk_is_reported(inspector, tmp_path):
    # A LIST/INFO chunk is text a player may read and display. This is the case
    # the scan exists for, and the one the old version buried under noise.
    base = _write_wav(tmp_path / "base.wav", _tone_frames(seconds=0.1)).read_bytes()
    body = b"INFO" + b"<script>evil()</script>" + b"\x00" * 5
    chunk = b"LIST" + struct.pack("<I", len(body)) + body
    spliced = bytearray(base[:12]) + chunk + base[12:]
    spliced[4:8] = struct.pack("<I", len(spliced) - 8)

    injected = tmp_path / "injected.wav"
    injected.write_bytes(bytes(spliced))

    assert any("<script" in w for w in _warnings(inspector, injected))


def test_a_non_riff_file_is_scanned_in_full(inspector, tmp_path):
    # Nothing in it is audio, so there is no payload to exempt.
    text = tmp_path / "actually-html.wav"
    text.write_bytes(b"nothing to see here\n<html><body>hi</body></html>")

    assert any("<html" in w for w in _warnings(inspector, text))


# --- degenerate inputs ---------------------------------------------------

def test_an_empty_file_does_not_crash(inspector, tmp_path):
    empty = tmp_path / "empty.wav"
    empty.write_bytes(b"")

    assert inspector.inspect_file(empty) is not None


def test_a_truncated_riff_header_does_not_crash(inspector, tmp_path):
    truncated = tmp_path / "truncated.wav"
    truncated.write_bytes(b"RIFF\x10")

    assert _warnings(inspector, truncated) == []


def test_a_chunk_claiming_an_absurd_size_terminates(inspector, tmp_path):
    # A hostile size field must not send the chunk walk past the mapping or
    # into a loop -- the scan runs on untrusted input by definition.
    hostile = tmp_path / "hostile.wav"
    hostile.write_bytes(b"RIFF" + struct.pack("<I", 0xFFFFFFF0) + b"WAVE"
                        + b"data" + struct.pack("<I", 0xFFFFFFF0) + b"\x00" * 32)

    assert inspector.inspect_file(hostile) is not None


def test_a_zero_length_chunk_does_not_loop_forever(inspector, tmp_path):
    empty_chunk = tmp_path / "zero.wav"
    empty_chunk.write_bytes(b"RIFF" + struct.pack("<I", 20) + b"WAVE"
                            + b"LIST" + struct.pack("<I", 0)
                            + b"data" + struct.pack("<I", 0))

    assert inspector.inspect_file(empty_chunk) is not None
