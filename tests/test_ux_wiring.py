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


def test_format_table_short_align_drops_no_columns():
    """audit-102: align=['right'] on a 2-column table zipped one format
    against two columns and the second column vanished from the output --
    a table that silently hides data."""
    from ux_improvements import TableFormatter

    out = TableFormatter.format_table(["a", "b"], [["1", "2"]], align=['right'])
    lines = out.splitlines()
    assert "b" in lines[0]
    assert "2" in lines[-1]


def test_format_table_wide_row_rejected_not_crash():
    """A row wider than the headers used to IndexError; short rows are
    normalised to the header width so no cell is ever dropped."""
    import pytest
    from ux_improvements import TableFormatter

    with pytest.raises(ValueError, match="3 cells for 2 headers"):
        TableFormatter.format_table(["a", "b"], [["1", "2", "EXTRA"]])

    out = TableFormatter.format_table(["a", "b"], [["1"], ["x", "y"]])
    lines = out.splitlines()
    assert len(lines) == 4  # header + separator + 2 rows
    assert "x" in lines[-1]
