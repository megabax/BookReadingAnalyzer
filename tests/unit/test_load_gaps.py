"""Тесты поиска пропусков дней в загрузках."""

from __future__ import annotations

from datetime import date

from author_today.storage.load_gaps import find_missing_days, format_date_ranges


def test_find_missing_days_tail_gap():
    missing = find_missing_days(
        date(2026, 6, 1),
        date(2026, 6, 5),
        {date(2026, 6, 4), date(2026, 6, 5)},
    )
    assert missing == [date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 3)]


def test_format_date_ranges_merges_contiguous():
    text = format_date_ranges(
        [
            date(2026, 6, 1),
            date(2026, 6, 2),
            date(2026, 6, 5),
        ]
    )
    assert text == "2026-06-01 .. 2026-06-02, 2026-06-05"
