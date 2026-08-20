"""Тесты подсветки заметок на тренде."""

from __future__ import annotations

from datetime import date

from author_today.analyze.completion_trend import (
    CompletionTrendPoint,
    CompletionTrendReport,
)
from author_today.storage.mssql_repo import BookNote
from author_today.ui.presenters.trend import notes_in_report_months


def _report() -> CompletionTrendReport:
    return CompletionTrendReport(
        book_id=1,
        period_start=date(2026, 6, 1),
        period_end=date(2026, 8, 31),
        target_chapter_order=5,
        target_chapter_name="Эпилог",
        baseline_chapter_order=None,
        skip_book_page=True,
        points=(
            CompletionTrendPoint(
                month_start=date(2026, 6, 1),
                month_end=date(2026, 6, 30),
                month_label="2026-06",
                target_chapter_order=5,
                target_chapter_name="Эпилог",
                target_views=10,
                baseline_views=100,
                pct_of_baseline=10.0,
            ),
            CompletionTrendPoint(
                month_start=date(2026, 7, 1),
                month_end=date(2026, 7, 31),
                month_label="2026-07",
                target_chapter_order=5,
                target_chapter_name="Эпилог",
                target_views=20,
                baseline_views=100,
                pct_of_baseline=20.0,
            ),
        ),
    )


def test_notes_in_report_months_filters_and_groups():
    notes = [
        BookNote(1, 1, date(2026, 7, 5), "реклама"),
        BookNote(2, 1, date(2026, 7, 20), "обложка"),
        BookNote(3, 1, date(2026, 5, 1), "вне периода"),
        BookNote(4, 1, date(2026, 8, 1), "месяц без точки тренда"),
    ]
    df = notes_in_report_months(notes, _report())

    assert list(df["month"]) == ["2026-07"]
    assert "реклама" in df.iloc[0]["label"]
    assert "обложка" in df.iloc[0]["label"]
