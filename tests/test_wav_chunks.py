"""WAV chunk-layout robustness (CHARTER Phase 8 — commercial-grade correctness).

Real-world WAV files routinely carry LIST/INFO metadata, JUNK padding (DAW
exports), fact chunks, 18-byte or extensible fmt bodies. The core previously
assumed "data starts at byte 44", silently producing wrong analysis and
corrupt processed output for such files. Each test compares a decorated file
against its byte-44 "plain twin" built from identical samples.

All fixtures are hand-assembled bytes (tests/_helpers.build_wav_bytes) — no
external files, stdlib only.
"""

import os
import struct

import pytest

import core
import main
from tests._helpers import sine_frames, write_wav_raw

TONE = sine_frames(count=4410)  # 0.1s @ 44100, mono int16 range

LIST_INFO = (b'LIST', b'INFO' + b'ICMT' + struct.pack('<I', 12) + b'a dawcomment')
ODD_JUNK = (b'JUNK', b'\x00\x01\x02')  # odd size → needs RIFF pad byte


def _plain(tmp_path, name="plain.wav", **kw):
    return write_wav_raw(tmp_path / name, frames=TONE, **kw)


# ---------------------------------------------------------------- analysis --

def test_list_chunk_analysis_matches_plain_twin(tmp_path):
    plain, _ = _plain(tmp_path)
    listy, off = write_wav_raw(tmp_path / "listy.wav", frames=TONE,
                               pre_data_chunks=[LIST_INFO])
    assert off > 44

    ra = core.analyze(str(plain))
    rb = core.analyze(str(listy))
    assert ra.success and rb.success, (ra.message, rb.message)
    assert rb.data.duration == pytest.approx(ra.data.duration)
    assert rb.data.peak_level == pytest.approx(ra.data.peak_level, abs=1e-6)
    assert rb.data.rms_level == pytest.approx(ra.data.rms_level, abs=1e-6)


def test_18_byte_fmt_duration_is_correct(tmp_path):
    wav, _ = write_wav_raw(tmp_path / "fmt18.wav", frames=TONE, fmt_variant="18")
    result = core.analyze(str(wav))
    assert result.success, result.message
    assert result.data.duration == pytest.approx(len(TONE) / 44100, rel=1e-6)


def test_extensible_pcm_is_accepted(tmp_path):
    wav, _ = write_wav_raw(tmp_path / "ext.wav", frames=TONE,
                           fmt_variant="extensible", format_tag=1)
    result = core.analyze(str(wav))
    assert result.success, result.message
    assert result.data.channels == 1
    assert result.data.bit_depth == 16


def test_odd_sized_junk_chunk_with_pad_byte(tmp_path):
    plain, _ = _plain(tmp_path)
    junky, _ = write_wav_raw(tmp_path / "junky.wav", frames=TONE,
                             pre_data_chunks=[ODD_JUNK])
    ra = core.analyze(str(plain))
    rb = core.analyze(str(junky))
    assert rb.success, rb.message
    assert rb.data.peak_level == pytest.approx(ra.data.peak_level, abs=1e-6)


def test_post_data_chunk_not_decoded_as_audio(tmp_path):
    plain, _ = _plain(tmp_path)
    trailed, _ = write_wav_raw(tmp_path / "trailed.wav", frames=TONE,
                               post_data_chunks=[(b'LIST', b'INFO' + b'\x7f' * 400)])
    ra = core.analyze(str(plain))
    rb = core.analyze(str(trailed))
    assert rb.success
    assert rb.data.duration == pytest.approx(ra.data.duration)
    assert rb.data.rms_level == pytest.approx(ra.data.rms_level, abs=1e-6)


def test_float32_wav_is_rejected_cleanly_by_core(tmp_path):
    wav, _ = write_wav_raw(tmp_path / "float.wav",
                           frames=[0.0, 0.5, -0.5, 0.25], format_tag=3)
    result = core.analyze(str(wav))
    assert not result.success  # PCM-only core: clean rejection, not garbage


def test_24bit_negative_sample_levels(tmp_path):
    # Full-scale negative 24-bit sample: peak must be 1.0, not garbage.
    frames = [0, -8388608, 0, 4194304]
    wav, _ = write_wav_raw(tmp_path / "s24.wav", frames=frames, bits=24)
    result = core.analyze(str(wav))
    assert result.success, result.message
    assert result.data.bit_depth == 24
    assert result.data.peak_level == pytest.approx(1.0, abs=1e-6)


def test_get_samples_for_analysis_honors_data_offset(tmp_path):
    plain, _ = _plain(tmp_path)
    listy, _ = write_wav_raw(tmp_path / "listy.wav", frames=TONE,
                             pre_data_chunks=[LIST_INFO])
    sa = core.get_samples_for_analysis(str(plain))
    sb = core.get_samples_for_analysis(str(listy))
    assert sa.success and sb.success
    assert sb.data["samples"] == pytest.approx(sa.data["samples"])


# -------------------------------------------------------------- processing --

def test_normalize_preserves_chunked_header_and_scales(tmp_path):
    listy, _ = write_wav_raw(tmp_path / "listy.wav", frames=TONE,
                             pre_data_chunks=[LIST_INFO])
    out = tmp_path / "out.wav"

    result = core.normalize(str(listy), str(out), 0.5)
    assert result.success, result.message

    reread = core.analyze(str(out))
    assert reread.success, reread.message
    assert reread.data.peak_level == pytest.approx(0.5, abs=0.01)
    # The LIST chunk survives in the output header prefix.
    assert b'dawcomment' in out.read_bytes()


def test_mono_conversion_on_chunked_stereo_file(tmp_path):
    stereo = sine_frames(count=2205, channels=2)
    src, _ = write_wav_raw(tmp_path / "st.wav", frames=stereo, channels=2,
                           pre_data_chunks=[LIST_INFO])
    out = tmp_path / "mono.wav"

    result = core.to_mono(str(src), str(out))
    assert result.success, result.message

    info = core.analyze(str(out))
    assert info.success, info.message
    assert info.data.channels == 1
    assert info.data.duration == pytest.approx(2205 / 44100, rel=1e-3)
    # Exact size: header prefix + mono data (16-bit → even, no pad).
    reparsed = core._processor._read_wav_header(str(out))
    assert os.path.getsize(out) == reparsed.data_offset + reparsed.data_size


def test_trim_silence_on_chunked_file(tmp_path):
    silence = [0] * 2000
    tone = sine_frames(count=2000)
    src, _ = write_wav_raw(tmp_path / "padded.wav",
                           frames=silence + tone + silence,
                           pre_data_chunks=[ODD_JUNK])
    out = tmp_path / "trimmed.wav"

    result = core.trim_silence(str(src), str(out), 0.05)
    assert result.success, result.message
    trimmed = core.analyze(str(out))
    assert trimmed.success
    assert trimmed.data.duration < (6000 / 44100) * 0.9  # silence actually removed


# ------------------------------------------------- main.py basic WAV loader --

@pytest.mark.skipif(not main.HAS_NUMPY, reason="_load_wav_basic decode needs numpy")
def test_load_wav_basic_decodes_float32(tmp_path):
    values = [0.0, 0.5, -0.5, 0.25]
    wav, _ = write_wav_raw(tmp_path / "f32.wav", frames=values, format_tag=3)
    audio, sr = main.AudioProcessor()._load_wav_basic(str(wav))
    assert sr == 44100
    assert list(audio[:4]) == pytest.approx(values)


@pytest.mark.skipif(not main.HAS_NUMPY, reason="_load_wav_basic decode needs numpy")
def test_load_wav_basic_decodes_24bit_signed(tmp_path):
    frames = [0, -8388608, 4194304]
    wav, _ = write_wav_raw(tmp_path / "s24.wav", frames=frames, bits=24)
    audio, sr = main.AudioProcessor()._load_wav_basic(str(wav))
    assert audio[1] == pytest.approx(-1.0, abs=1e-6)
    assert audio[2] == pytest.approx(0.5, abs=1e-6)


@pytest.mark.skipif(not main.HAS_NUMPY, reason="_load_wav_basic decode needs numpy")
def test_load_wav_basic_8bit_unsigned_offset(tmp_path):
    frames = [0, 127, -128]  # stored as 128, 255, 0
    wav, _ = write_wav_raw(tmp_path / "u8.wav", frames=frames, bits=8)
    audio, sr = main.AudioProcessor()._load_wav_basic(str(wav))
    assert audio[0] == pytest.approx(0.0, abs=0.01)
    assert audio[2] == pytest.approx(-1.0, abs=0.01)
