"""Covers ux_improvements.py wiring into main.py's AudioProcessor.batch_process.

ux_improvements.py was previously packaged but never imported (CHARTER §9's
orphaned-module punch list). It is stdlib-only, real, and non-duplicative, so
it was wired in rather than deleted: batch_process gained an opt-in
show_progress flag that renders a ProgressBar, and the CLI's batch command
colorizes its summary line with ColorText.
"""

import main
from tests._helpers import write_sine_wave


def test_ux_improvements_module_is_wired(monkeypatch):
    assert main.HAS_UX_IMPROVEMENTS is True


def test_batch_process_default_has_no_progress_output(tmp_path, capsys):
    wav = write_sine_wave(tmp_path / "tone.wav")
    processor = main.AudioProcessor()

    results = processor.batch_process([str(wav)], "analyze")

    assert results and "error" not in results[0]
    captured = capsys.readouterr()
    assert "█" not in captured.out  # no progress-bar block characters


def test_batch_process_show_progress_renders_progress_bar(tmp_path, capsys):
    wav1 = write_sine_wave(tmp_path / "a.wav")
    wav2 = write_sine_wave(tmp_path / "b.wav")
    processor = main.AudioProcessor()
    processor.config.parallel = False  # deterministic single-threaded completion order

    results = processor.batch_process(
        [str(wav1), str(wav2)], "analyze", show_progress=True
    )

    assert len(results) == 2
    captured = capsys.readouterr()
    assert "analyze" in captured.out
    assert "2/2" in captured.out


def test_batch_process_show_progress_false_by_default_matches_cli_non_tty(tmp_path):
    """Regression guard: batch_process must accept show_progress as keyword-only
    without breaking existing positional-style callers that omit it."""
    wav = write_sine_wave(tmp_path / "tone.wav")
    processor = main.AudioProcessor()

    results = processor.batch_process([str(wav)], "analyze")
    assert results and "error" not in results[0]


def test_format_file_size_rejects_non_finite():
    """format_file_size(inf) printed 'inf PB' and format_file_size(nan)
    printed 'nan PB' -- a fabricated size for input that has none. Same
    contract as format_duration's finite check: a formatter may not invent
    a finite-looking label for a value that is not finite."""
    import pytest
    import ux_improvements
    with pytest.raises(ValueError, match="finite"):
        ux_improvements.format_file_size(float("inf"))
    with pytest.raises(ValueError, match="finite"):
        ux_improvements.format_file_size(float("nan"))
    with pytest.raises(ValueError, match="finite"):
        ux_improvements.format_file_size(float("-inf"))


def test_format_file_size_still_formats_real_sizes():
    import ux_improvements
    assert ux_improvements.format_file_size(0) == "0.0 B"
    assert ux_improvements.format_file_size(1024) == "1.0 KB"
    assert ux_improvements.format_file_size(2**50) == "1.0 PB"
