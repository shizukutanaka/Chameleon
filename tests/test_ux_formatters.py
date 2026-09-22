"""TableFormatter must not crash on -- or silently drop -- ragged rows.

Found on the ux_improvements audit: ``format_table`` iterated row cells
against the header-width list, so a row with more cells than headers died
on a bare ``IndexError``, and a row with fewer cells silently rendered a
table whose later columns went missing -- both from the same unchecked
assumption that every row matches the header count.
"""

import pytest

from ux_improvements import TableFormatter


def test_wide_row_raises_value_error_naming_the_row():
    # An IndexError named nothing; the caller needs the offending row.
    with pytest.raises(ValueError, match="row 1 has 3 cells"):
        TableFormatter.format_table(
            ["A", "B"], [["1", "2"], ["1", "2", "3"]])


def test_narrow_row_keeps_all_columns_aligned():
    # Missing trailing cells used to make the row shorter than the header,
    # leaving every subsequent column unreadable. Padding keeps the grid.
    table = TableFormatter.format_table(["A", "B"], [["x"]])
    lines = table.split("\n")
    assert len(lines) == 3            # header, rule, one row
    assert lines[2].count("|") == lines[0].count("|") == 1


def test_full_rows_are_unchanged():
    table = TableFormatter.format_table(
        ["A", "B"], [["1", "2"], ["longer", "22"]])
    assert "longer" in table and "22" in table
