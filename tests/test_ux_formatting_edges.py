"""Display-layer helpers must degrade on malformed input, not crash.

At HEAD:
- ``TableFormatter.format_table`` raised IndexError when a row had more
  cells than headers (``widths[i]`` out of range), and silently
  misaligned rows with fewer cells.
- ``format_duration(nan)`` fell through every ``<`` comparison into the
  hours branch's ``int(seconds / 3600)`` -- ValueError.
- ``format_file_size(nan)`` divided NaN by 1024 four times and returned
  "nan PB".
"""
import math

import pytest

from ux_improvements import (
    TableFormatter,
    format_duration,
    format_file_size,
)


def test_table_with_extra_cells_does_not_crash():
    out = TableFormatter.format_table(["a", "b"], [["x", "y", "EXTRA"]])
    assert "EXTRA" not in out
    assert "x" in out and "y" in out


def test_table_with_missing_cells_pads():
    out = TableFormatter.format_table(["aa", "bb"], [["x"]])
    lines = out.split("\n")
    # header, separator, one row -- the row still gets both columns
    assert len(lines) == 3
    assert "|" in lines[2]


def test_table_normal_case_unchanged():
    out = TableFormatter.format_table(
        ["name", "size"], [["f.wav", "1.2 MB"]], align=["left", "right"])
    assert "name" in out and "f.wav" in out


def test_format_duration_nan_and_negative():
    assert format_duration(float("nan")) == "unknown"
    assert format_duration(float("inf")) == "unknown"
    assert format_duration(-5) == "unknown"


def test_format_duration_normal():
    assert format_duration(0.5) == "500ms"
    assert format_duration(90) == "1m 30s"
    assert format_duration(3700) == "1h 1m"


def test_format_file_size_nan_and_negative():
    assert format_file_size(float("nan")) == "unknown"
    assert format_file_size(-100) == "unknown"


def test_format_file_size_normal():
    assert format_file_size(512) == "512.0 B"
    assert format_file_size(1536000) == "1.5 MB"
