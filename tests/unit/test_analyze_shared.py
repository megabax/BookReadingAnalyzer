"""Unit-тесты для chapter_filters и formatting."""

from __future__ import annotations

from author_today.analyze.chapter_filters import filter_chapter_rows, is_book_page
from author_today.analyze.formatting import fmt_decimal_ru, fmt_pvalue, pct, pct_column_label


def test_is_book_page():
    assert is_book_page("Страница книги")
    assert is_book_page("  страница книги  ")
    assert not is_book_page("Глава 1")


def test_filter_chapter_rows_skips_book_page():
    rows = [
        (2, "Глава 1", 10),
        (1, "Страница книги", 100),
        (3, "Глава 2", 5),
    ]
    filtered = filter_chapter_rows(rows, skip_book_page=True)
    assert filtered == [(2, "Глава 1", 10), (3, "Глава 2", 5)]


def test_pct_and_formatting():
    assert pct(50, 100) == 50.0
    assert pct(1, 3, places=2) == 33.33
    assert pct(1, 0) == 0.0
    assert pct_column_label(None) == "% от 1-й"
    assert pct_column_label(2) == "% от гл.2"
    assert fmt_decimal_ru(12.5, 1) == "12,5"
    assert fmt_pvalue(None) == "—"
    assert fmt_pvalue(0.0123) == "0,0123"
