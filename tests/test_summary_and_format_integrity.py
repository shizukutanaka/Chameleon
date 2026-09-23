"""Regression tests for the cycle-4 measured fixes: batch summary
double-counting, MIDI empty-input/range edges, and the enhanced-integrity
checks that rejected every file or crashed on every read.

Each test's docstring records the measured defect it pins down.
"""

import os

import pytest

import core
import midi_analysis
from tests._helpers import write_sine_wave


class TestBatchSummaryErrorCounting:
    """`process_directory` appended the same analysis to summary['errors']
    twice for every exception-path failure: once directly in the except
    block and again via result.data['analysis'] below, so the persisted
    batch state reported 2x the real failure count (measured: 1 file, 1
    failure, len(summary['errors']) == 2)."""

    def test_exception_failure_is_counted_once_in_summary(self, tmp_path, monkeypatch):
        write_sine_wave(tmp_path / "a.wav", duration=0.2, amplitude=0.3)
        processor = core.BatchProcessor()

        def boom(_path):
            raise OSError("simulated disk failure")

        monkeypatch.setattr(processor.processor, "analyze", boom)
        results = processor.process_directory(str(tmp_path), "analyze",
                                              skip_errors=True)

        summary = results[-1].data["summary"]
        assert summary["failed"] == 1
        assert len(summary["errors"]) == 1

    def test_clean_run_reports_zero_errors(self, tmp_path):
        # Control: the success path never produced the double-append and
        # must keep reporting zero.
        write_sine_wave(tmp_path / "a.wav", duration=0.2, amplitude=0.3)
        processor = core.BatchProcessor()
        results = processor.process_directory(str(tmp_path), "analyze")
        summary = results[-1].data["summary"]
        assert summary["errors"] == []


class TestMidiEdges:
    def test_detect_chords_on_empty_input_returns_empty(self):
        # max() over an empty sequence raised ValueError; sibling APIs
        # (analyze_rhythm, analyze_harmony) already treat empty input as
        # "nothing to report".
        analyzer = midi_analysis.MIDIAnalyzer()
        assert analyzer.detect_chords([]) == []

    def test_analyze_rhythm_empty_honors_configured_time_signature(self):
        # The empty-notes path hardcoded (4, 4) while the one-note and
        # no-usable-interval paths returned self.config.time_signature --
        # a configured (3, 4) came back (4, 4) only when the input was
        # empty.
        analyzer = midi_analysis.MIDIAnalyzer(
            midi_analysis.MIDIConfig(time_signature=(3, 4)))
        assert analyzer.analyze_rhythm([])["time_signature"] == (3, 4)

    def test_midi_writer_clamps_out_of_range_pitch_and_velocity(self, tmp_path):
        # Pitch/velocity are single MIDI data bytes (0-127). A caller's
        # out-of-range MIDINote emitted the raw value: 200 produced a byte
        # >= 0x80 in a data position (unparseable stream for any real MIDI
        # reader) and a negative pitch aborted the write outright.
        analyzer = midi_analysis.MIDIAnalyzer()
        out = tmp_path / "clamped.mid"
        note = midi_analysis.MIDINote(pitch=200, velocity=300,
                                      start_time=0.0, duration=0.5)
        assert analyzer.generate_midi_file([note], str(out)) is True
        data = out.read_bytes()
        note_on = data.find(b"\x90")
        assert note_on != -1
        # Clamped to the MIDI data-byte maximum, not emitted raw.
        assert data[note_on + 1:note_on + 3] == bytes([127, 127])

    def test_midi_writer_accepts_ordinary_notes_unchanged(self, tmp_path):
        # Control: in-range values pass through unmodified.
        analyzer = midi_analysis.MIDIAnalyzer()
        out = tmp_path / "ok.mid"
        note = midi_analysis.MIDINote(pitch=67, velocity=80,
                                      start_time=0.0, duration=0.5)
        assert analyzer.generate_midi_file([note], str(out)) is True
        data = out.read_bytes()
        note_on = data.find(b"\x90")
        assert data[note_on + 1:note_on + 3] == bytes([67, 80])


class TestEnhancedIntegrityChecks:
    """`check_file_integrity` returned False for 100% of files: its
    permission test held `mode & 0o777` against the FULL st_mode (which
    also carries file-type bits), always true. And if a file ever got
    that far, `_calculate_file_entropy` raised AttributeError calling
    `float.bit_length()` -- the expression was never Shannon entropy."""

    def test_entropy_is_zero_for_single_repeated_byte(self, tmp_path):
        f = tmp_path / "constant.bin"
        f.write_bytes(b"\x01" * 1000)
        # Correct Shannon entropy of one distinct byte is exactly 0.
        assert core.EnhancedSecurityValidator._calculate_file_entropy(str(f)) == 0.0

    def test_entropy_of_random_data_is_high(self, tmp_path):
        f = tmp_path / "random.bin"
        f.write_bytes(os.urandom(10000))
        entropy = core.EnhancedSecurityValidator._calculate_file_entropy(str(f))
        # Near-uniform bytes: Shannon entropy approaches 8 bits/byte.
        assert entropy > 7.5

    def test_normal_file_passes_integrity(self, tmp_path):
        f = tmp_path / "normal.wav"
        f.write_bytes(b"RIFF" + b"\x24\x00\x00\x00WAVE" + b"\x01" * 100)
        # Measured: every file failed before, because the permission mask
        # compared against file-type bits too.
        assert core.EnhancedSecurityValidator.check_file_integrity(str(f)) is True

    def test_high_entropy_file_fails_integrity(self, tmp_path):
        f = tmp_path / "encrypted.bin"
        f.write_bytes(os.urandom(10000))
        assert core.EnhancedSecurityValidator.check_file_integrity(str(f)) is False

    def test_setuid_file_fails_integrity(self, tmp_path):
        f = tmp_path / "suid.wav"
        f.write_bytes(b"\x01" * 100)
        f.chmod(0o4755)
        if os.name != "posix":
            pytest.skip("permission bits are a posix check")
        assert core.EnhancedSecurityValidator.check_file_integrity(str(f)) is False


class TestBatchJobRequestValidation:
    def test_empty_file_list_is_rejected(self):
        # An empty `files` list passed validation and produced a batch job
        # that completed instantly with progress 0.0 -- a record of work
        # never requested.
        pytest.importorskip("fastapi")
        pydantic = pytest.importorskip("pydantic")
        import api_server
        with pytest.raises(pydantic.ValidationError):
            api_server.BatchJobRequest(files=[], operation="analyze")

    def test_nonempty_file_list_still_validates(self):
        pytest.importorskip("fastapi")
        import api_server
        req = api_server.BatchJobRequest(files=["a.wav"], operation="analyze")
        assert req.files == ["a.wav"]
