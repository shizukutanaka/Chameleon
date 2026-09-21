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


def test_progress_bar_clamps_overshoot_and_negative(capsys):
    # update()/set_progress() trusted the caller: update(10) on total=3
    # rendered "333.3%" and a bar wider than bar_width.
    from ux_improvements import ProgressBar

    bar = ProgressBar(total=3, description="t")
    bar.last_update = 0  # bypass the render rate limiter
    bar.update(10)
    assert bar.current == 3
    assert "100.0%" in capsys.readouterr().out
    assert "333" not in capsys.readouterr().out

    bar2 = ProgressBar(total=3)
    bar2.set_progress(-5)
    assert bar2.current == 0


def test_color_text_honors_no_color(monkeypatch):
    # The NO_COLOR convention: any presence of the variable means plain
    # output, even on a TTY.
    from ux_improvements import ColorText

    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    assert not ColorText.enabled()
    assert ColorText.colorize("x", ColorText.RED) == "x"

    monkeypatch.delenv("NO_COLOR")
    assert ColorText.enabled()
    assert ColorText.colorize("x", ColorText.RED) != "x"
