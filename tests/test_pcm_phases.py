"""Equivalence checks for the stdlib PCM decode and encode phases."""

import random
import wave
from array import array

import pytest

import core
from tests._helpers import build_wav_bytes


BIT_DEPTHS = (8, 16, 24, 32)
CHANNEL_COUNTS = (1, 2)


def _sample_bounds(bit_depth):
    minimum = -(1 << (bit_depth - 1))
    return minimum, (1 << (bit_depth - 1)) - 1


def _random_samples(bit_depth, channels, frames=13):
    minimum, maximum = _sample_bounds(bit_depth)
    rng = random.Random(bit_depth * 100 + channels)
    sample_count = frames * channels
    samples = [minimum, maximum]
    samples.extend(
        rng.randint(minimum, maximum) for _ in range(sample_count - len(samples))
    )
    return samples


def _reference_levels(payload, bit_depth, sample_limit=None):
    processor = core.WAVProcessor
    bytes_per_sample = bit_depth // 8
    max_value = 0.0
    sum_squares = 0.0
    sample_count = 0

    for offset in range(0, len(payload), bytes_per_sample):
        if sample_limit is not None and sample_count >= sample_limit:
            break
        sample = processor._decode_sample_bytes(
            payload[offset:offset + bytes_per_sample], bit_depth
        )
        if sample is None:
            continue
        normalized = processor._normalize_amplitude(sample, bit_depth)
        max_value = max(max_value, normalized)
        sum_squares += normalized * normalized
        sample_count += 1

    if sample_count == 0:
        return 0.0, 0.0
    return max_value, (sum_squares / sample_count) ** 0.5


def _read_payload(path, info):
    contents = path.read_bytes()
    return contents[info.data_offset:info.data_offset + info.data_size]


@pytest.mark.parametrize("bit_depth", BIT_DEPTHS)
@pytest.mark.parametrize("channels", CHANNEL_COUNTS)
def test_decode_pcm_frames_matches_per_sample_decode(bit_depth, channels):
    samples = _random_samples(bit_depth, channels)
    payload = b"".join(
        core.WAVProcessor._encode_sample_value(sample, bit_depth)
        for sample in samples
    )
    bytes_per_sample = bit_depth // 8

    actual = core.WAVProcessor._decode_pcm_frames(payload, bit_depth)
    expected = [
        core.WAVProcessor._decode_sample_bytes(
            payload[offset:offset + bytes_per_sample], bit_depth
        )
        for offset in range(0, len(payload), bytes_per_sample)
    ]

    assert actual == expected


@pytest.mark.parametrize("bit_depth", BIT_DEPTHS)
@pytest.mark.parametrize("channels", CHANNEL_COUNTS)
def test_encode_pcm_samples_matches_per_sample_encode(bit_depth, channels):
    minimum, maximum = _sample_bounds(bit_depth)
    rng = random.Random(10_000 + bit_depth * 100 + channels)
    samples = [
        minimum - 100, minimum, -1, 0, 1, maximum, maximum + 100,
    ]
    samples.extend(
        rng.randint(minimum - 100, maximum + 100)
        for _ in range(13 * channels - len(samples))
    )

    actual = core.WAVProcessor._encode_pcm_samples(samples, bit_depth)
    expected = b"".join(
        core.WAVProcessor._encode_sample_value(sample, bit_depth)
        for sample in samples
    )

    assert actual == expected


@pytest.mark.parametrize("bit_depth", BIT_DEPTHS)
@pytest.mark.parametrize("channels", CHANNEL_COUNTS)
def test_normalize_and_levels_match_per_sample_reference(
    tmp_path, bit_depth, channels
):
    source = tmp_path / "input.wav"
    output = tmp_path / "normalized.wav"
    samples = _random_samples(bit_depth, channels)
    wav_bytes, _ = build_wav_bytes(
        frames=samples, channels=channels, bits=bit_depth
    )
    source.write_bytes(wav_bytes)

    processor = core.WAVProcessor()
    input_info = processor._read_wav_header(str(source))
    assert input_info is not None
    input_payload = _read_payload(source, input_info)
    reference_peak, reference_rms = _reference_levels(input_payload, bit_depth)
    assert processor._calculate_levels_safe(str(source), input_info) == (
        reference_peak, reference_rms
    )

    target_peak = 0.83
    gain = target_peak / reference_peak
    bytes_per_sample = bit_depth // 8
    expected_payload = b"".join(
        core.WAVProcessor._encode_sample_value(
            int(round(
                core.WAVProcessor._decode_sample_bytes(
                    input_payload[offset:offset + bytes_per_sample], bit_depth
                ) * gain
            )),
            bit_depth,
        )
        for offset in range(0, len(input_payload), bytes_per_sample)
    )

    result = core.normalize(str(source), str(output), target_peak)
    assert result.success, result.message

    output_info = processor._read_wav_header(str(output))
    assert output_info is not None
    actual_payload = _read_payload(output, output_info)
    assert actual_payload == expected_payload
    output_bytes = output.read_bytes()
    expected_pad = b"\x00" if output_info.data_size % 2 else b""
    assert output_bytes[output_info.data_offset + output_info.data_size:] == expected_pad


def test_decode_pcm_frames_rejects_unsupported_or_partial_samples():
    assert core.WAVProcessor._decode_pcm_frames(b"\x00", 12) is None
    assert core.WAVProcessor._decode_pcm_frames(b"\x00", 16) is None
    assert core.WAVProcessor._decode_pcm_frames(b"\x00\x00\x00", 32) is None


def test_calculate_levels_stops_at_one_million_samples(tmp_path):
    source = tmp_path / "over-limit.wav"
    samples = array('h', [0]) * 1_000_002
    samples[1_000_000] = 32767
    with wave.open(str(source), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(48000)
        handle.writeframes(samples.tobytes())

    processor = core.WAVProcessor()
    info = processor._read_wav_header(str(source))
    assert info is not None
    payload = _read_payload(source, info)
    expected = _reference_levels(payload, 16, sample_limit=1_000_000)

    assert expected == (0.0, 0.0)
    assert processor._calculate_levels_safe(str(source), info) == expected
