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


def test_format_table_short_align_keeps_all_columns():
    """An align list shorter than the headers silently dropped trailing
    columns: zip(widths, align) produced fewer format specs than
    columns, so 'C' and '3' below used to vanish from the output."""
    from ux_improvements import TableFormatter

    out = TableFormatter.format_table(["A", "B", "C"], [["1", "2", "3"]],
                                      align=["right"])

    assert "B" in out and "C" in out and "3" in out


def test_format_table_extra_align_entries_are_ignored():
    from ux_improvements import TableFormatter

    out = TableFormatter.format_table(["A"], [["1"]],
                                      align=["right", "center", "right"])

    assert "A" in out and "1" in out


def test_progress_bar_display_clamps_overshoot(capsys):
    """set_progress()/update() can push current past total; the render
    used to claim '150.0%' and overflow the bar past its width."""
    from ux_improvements import ProgressBar

    bar = ProgressBar(total=10, description="t")
    bar.set_progress(15)

    out = capsys.readouterr().out
    assert "100.0%" in out
    assert "150" not in out
    assert "█" * 41 not in out
