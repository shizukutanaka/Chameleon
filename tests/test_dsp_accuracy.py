"""Regression tests for the research-backed DSP accuracy fixes.

These lock in three standard-conformance improvements to the stdlib-only
signal path:

* A1 - spectral_utils.analyze_spectrum now applies a Hann window before the
  transform (rectangular windows leak energy across bins) and refines each
  detected peak with parabolic interpolation (sub-bin frequency accuracy).
* A2 - midi_analysis._estimate_pitch now uses YIN instead of a global-maximum
  autocorrelation, which removes the classic octave errors on tones with a
  strong harmonic.

All tests are pure standard library so they run in the default install.
"""

import math

import spectral_utils
from midi_analysis import MIDIAnalyzer


def _sine(frequency, sample_rate, count, amplitude=1.0, phase=0.0):
    return [amplitude * math.sin(2 * math.pi * frequency * i / sample_rate + phase)
            for i in range(count)]


# --- A1: windowing + parabolic interpolation --------------------------------

def test_hann_window_shape():
    window = spectral_utils._hann_window(9)
    assert window[0] == 0.0
    assert window[-1] == 0.0
    assert abs(window[4] - 1.0) < 1e-9          # peak at the centre
    # Symmetric taper.
    for left, right in zip(window, reversed(window)):
        assert abs(left - right) < 1e-9


def test_hann_window_degenerate_lengths():
    assert spectral_utils._hann_window(0) == []
    assert spectral_utils._hann_window(1) == [1.0]


def test_peak_frequency_is_sub_bin_accurate():
    # bin_width = sample_rate / N = 8000 / 1000 = 8 Hz. 436 Hz sits almost
    # exactly between bin 54 (432 Hz) and bin 55 (440 Hz), so plain bin-snapping
    # is off by ~4 Hz. Parabolic interpolation must recover it far tighter.
    sample_rate, count, freq = 8000, 1000, 436.0
    samples = _sine(freq, sample_rate, count)

    report = spectral_utils.analyze_spectrum(samples, sample_rate, max_peaks=1)

    assert report.dominant_peaks
    detected = report.dominant_peaks[0].frequency_hz
    # Comfortably better than the 4 Hz worst case of nearest-bin selection.
    assert abs(detected - freq) < 2.5, detected


def test_windowing_reduces_spectral_leakage():
    # A tone whose frequency is not an exact bin centre leaks badly under a
    # rectangular window. With a Hann window the energy stays concentrated, so
    # the dominant peak's magnitude dwarfs a distant off-peak bin.
    sample_rate, count = 8000, 1000
    samples = _sine(437.0, sample_rate, count)

    report = spectral_utils.analyze_spectrum(samples, sample_rate, max_peaks=5)
    peaks = report.dominant_peaks
    assert peaks
    top = peaks[0].magnitude
    # Every secondary peak is much weaker than the fundamental (low leakage).
    for other in peaks[1:]:
        assert other.magnitude < 0.5 * top


def test_quantisation_floor_is_not_reported_as_dominant():
    # A 16-bit sine truncated with int() carries odd harmonics ~96 dB down.
    # Before the relative floor, all five reported "dominant frequencies" but
    # the first were these quantisation artefacts.
    sample_rate, count, freq = 44100, 4096, 440.0
    samples = [int(12000 * math.sin(2 * math.pi * freq * i / sample_rate))
               for i in range(count)]

    report = spectral_utils.analyze_spectrum(samples, sample_rate, max_peaks=5)

    assert len(report.dominant_peaks) == 1, [
        (p.frequency_hz, p.relative_db(report.dominant_peaks[0]))
        for p in report.dominant_peaks
    ]
    assert abs(report.dominant_peaks[0].frequency_hz - freq) < 2.0

    # Lowering the floor must bring the artefacts back, proving the floor --
    # not the detector -- is what removes them.
    permissive = spectral_utils.analyze_spectrum(
        samples, sample_rate, max_peaks=5, min_relative_db=-120.0
    )
    assert len(permissive.dominant_peaks) == 5


def test_real_harmonics_survive_the_peak_floor():
    sample_rate, count = 44100, 4096
    fundamental = 440.0
    samples = [
        math.sin(2 * math.pi * fundamental * i / sample_rate)
        + 0.1 * math.sin(2 * math.pi * 3 * fundamental * i / sample_rate)      # -20 dB
        + 1e-4 * math.sin(2 * math.pi * 5 * fundamental * i / sample_rate)     # -80 dB
        for i in range(count)
    ]

    report = spectral_utils.analyze_spectrum(samples, sample_rate, max_peaks=5)
    peaks = report.dominant_peaks

    assert [round(p.frequency_hz / fundamental) for p in peaks] == [1, 3]
    # Levels come from bin-centre magnitudes, so two tones at different
    # fractional bin offsets differ by up to the Hann scalloping loss (~1.4 dB).
    assert abs(peaks[1].relative_db(peaks[0]) - (-20.0)) < 1.5
    assert peaks[0].relative_db(peaks[0]) == 0.0


# --- A2: YIN pitch detection ------------------------------------------------

def _cents(f_detected, f_true):
    return 1200.0 * math.log2(f_detected / f_true)


def test_yin_detects_pure_tones_within_a_few_cents():
    analyzer = MIDIAnalyzer()
    sample_rate = 44100
    frame = 2048
    for freq in (220.0, 440.0, 880.0):
        samples = _sine(freq, sample_rate, frame)
        detected = analyzer._estimate_pitch(samples, sample_rate)
        assert detected is not None, f"no pitch for {freq} Hz"
        assert abs(_cents(detected, freq)) < 20.0, (freq, detected)


def test_yin_picks_fundamental_not_the_louder_harmonic():
    # Fundamental at 200 Hz with a *louder* second harmonic at 400 Hz. A naive
    # global-maximum autocorrelation is prone to locking onto the 400 Hz
    # (octave-up) period here; YIN must report the true fundamental.
    analyzer = MIDIAnalyzer()
    sample_rate = 44100
    frame = 2048
    samples = [a + b for a, b in zip(
        _sine(200.0, sample_rate, frame, amplitude=1.0),
        _sine(400.0, sample_rate, frame, amplitude=1.6),
    )]

    detected = analyzer._estimate_pitch(samples, sample_rate)

    assert detected is not None
    assert 190.0 < detected < 210.0, detected   # ~200, not ~400


def test_yin_returns_none_on_silence():
    analyzer = MIDIAnalyzer()
    detected = analyzer._estimate_pitch([0.0] * 2048, 44100)
    assert detected is None
