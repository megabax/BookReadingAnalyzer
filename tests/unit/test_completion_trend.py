"""Тесты тренда дочитывания."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from author_today.analyze.completion_trend import (
    build_completion_trend,
    list_chapter_options,
    resolve_target_chapter_order,
    save_completion_trend_csv,
    trend_point_from_snapshot,
)
from author_today.domain.models import ReadSnapshot
from author_today.errors import DataNotFoundError


def _make_snap(
    month_start: date,
    month_end: date,
    cover: int,
    ch1: int,
    ch2: int,
) -> ReadSnapshot:
    return ReadSnapshot(
        book_id=1,
        period_start=month_start,
        period_end=month_end,
        fetched_at=datetime(2025, 1, 1),
        dates=(month_start,),
        chapters=("Страница книги", "Глава 1", "Глава 2"),
        values=((cover,), (ch1,), (ch2,)),
        chapter_orders=(1, 2, 3),
    )


def test_list_chapter_options_skips_cover():
    rows = [
        (1, "Страница книги", 100),
        (2, "Глава 1", 80),
        (3, "Глава 2", 40),
    ]
    assert list_chapter_options(rows, skip_book_page=True) == [
        (2, "Глава 1"),
        (3, "Глава 2"),
    ]


def test_resolve_target_defaults_to_last():
    rows = [
        (1, "Страница книги", 100),
        (2, "Глава 1", 80),
        (3, "Глава 2", 40),
    ]
    assert resolve_target_chapter_order(rows, skip_book_page=True) == 3
    assert resolve_target_chapter_order(rows, skip_book_page=False) == 3


def test_resolve_target_explicit():
    rows = [(2, "Глава 1", 80), (3, "Глава 2", 40)]
    assert resolve_target_chapter_order(rows, target_chapter_order=2) == 2


def test_resolve_target_missing_raises():
    rows = [(2, "Глава 1", 80)]
    with pytest.raises(DataNotFoundError, match="chapter_order=99"):
        resolve_target_chapter_order(rows, target_chapter_order=99)


def test_trend_point_from_snapshot_last_chapter():
    snap = _make_snap(date(2025, 7, 1), date(2025, 7, 31), 100, 80, 40)
    point = trend_point_from_snapshot(
        snap,
        target_chapter_order=3,
        skip_book_page=True,
    )
    assert point is not None
    assert point.month_label == "2025-07"
    assert point.target_views == 40
    assert point.baseline_views == 80
    assert point.pct_of_baseline == 50.0


def test_trend_point_missing_target_returns_none():
    snap = _make_snap(date(2025, 7, 1), date(2025, 7, 31), 100, 80, 40)
    assert (
        trend_point_from_snapshot(
            snap,
            target_chapter_order=99,
            skip_book_page=True,
        )
        is None
    )


def test_build_completion_trend_monthly():
    jul = _make_snap(date(2025, 7, 1), date(2025, 7, 31), 100, 100, 50)
    aug = _make_snap(date(2025, 8, 1), date(2025, 8, 31), 100, 80, 20)
    catalog = [
        (1, "Страница книги", 200),
        (2, "Глава 1", 180),
        (3, "Глава 2", 70),
    ]
    report = build_completion_trend(
        [jul, aug],
        book_id=1,
        period_start=date(2025, 7, 1),
        period_end=date(2025, 8, 31),
        catalog_rows=catalog,
        target_chapter_order=None,
        skip_book_page=True,
    )
    assert report.target_chapter_order == 3
    assert report.target_chapter_name == "Глава 2"
    assert len(report.points) == 2
    assert report.points[0].pct_of_baseline == 50.0
    assert report.points[1].pct_of_baseline == 25.0


def test_build_completion_trend_custom_chapter():
    jul = _make_snap(date(2025, 7, 1), date(2025, 7, 31), 100, 80, 40)
    catalog = [
        (1, "Страница книги", 100),
        (2, "Глава 1", 80),
        (3, "Глава 2", 40),
    ]
    report = build_completion_trend(
        [jul],
        book_id=1,
        period_start=date(2025, 7, 1),
        period_end=date(2025, 7, 31),
        catalog_rows=catalog,
        target_chapter_order=2,
        skip_book_page=True,
        baseline_chapter_order=2,
    )
    assert report.target_chapter_order == 2
    assert report.points[0].pct_of_baseline == 100.0


def test_build_completion_trend_empty_raises():
    catalog = [(2, "Глава 1", 80), (3, "Глава 2", 40)]
    with pytest.raises(DataNotFoundError, match="Нет месячных точек"):
        build_completion_trend(
            [],
            book_id=1,
            period_start=date(2025, 7, 1),
            period_end=date(2025, 7, 31),
            catalog_rows=catalog,
            skip_book_page=True,
        )


def test_save_completion_trend_csv(tmp_path):
    jul = _make_snap(date(2025, 7, 1), date(2025, 7, 31), 100, 80, 40)
    catalog = [
        (1, "Страница книги", 100),
        (2, "Глава 1", 80),
        (3, "Глава 2", 40),
    ]
    report = build_completion_trend(
        [jul],
        book_id=42,
        period_start=date(2025, 7, 1),
        period_end=date(2025, 7, 31),
        catalog_rows=catalog,
        skip_book_page=True,
    )
    out = save_completion_trend_csv(report, tmp_path / "t.csv")
    text = out.read_text(encoding="utf-8-sig")
    assert "2025-07" in text
    assert "Глава 2" in text
    assert "50,0" in text
    assert ";" in text
