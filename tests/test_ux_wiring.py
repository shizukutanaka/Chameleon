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


def test_progress_bar_eta_format_carries_minutes():
    """The ETA helper's minutes+seconds split must carry: formatting
    ``seconds / 60`` and ``seconds % 60`` independently printed a second
    field of "60" whenever the seconds fraction rounded up (119.7 ->
    "2m 60s", 3599.6 -> "60m 60s") -- a duration that does not exist."""
    from ux_improvements import ProgressBar

    fmt = ProgressBar._format_time

    assert fmt(119.7) == "2m 0s"   # was "2m 60s"
    assert fmt(3599.6) == "60m 0s"  # was "60m 60s"
    # Below the carry window the split is unchanged.
    assert fmt(59.4) == "59s"
    assert fmt(119.4) == "1m 59s"
    assert fmt(60.0) == "1m 0s"
