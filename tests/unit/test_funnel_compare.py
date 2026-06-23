"""Тесты сравнения воронок за два периода."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from author_today.analyze.funnel_compare import (
    compare_funnel_periods,
    daily_matrix_from_json,
    save_funnel_compare_csv,
)

DailyMatrix = dict[date, dict[int, tuple[str, int]]]


def _matrix(days: list[tuple[date, dict[int, tuple[str, int]]]]) -> DailyMatrix:
    return dict(days)


def _day(d: str, base_views: int, ch3_views: int) -> tuple[date, dict[int, tuple[str, int]]]:
    read_date = date.fromisoformat(d)
    return read_date, {
        1: ("Страница книги", base_views * 2),
        2: ("Глава 1", base_views),
        3: ("Глава 2", ch3_views),
    }


def test_daily_pct_constant_mean():
    matrix = _matrix([_day("2025-07-01", 100, 50), _day("2025-07-02", 100, 50)])
    report = compare_funnel_periods(
        matrix,
        matrix,
        baseline_chapter_order=2,
        skip_book_page=True,
    )
    row = next(r for r in report.rows if r.site_chapter_order == 3)
    assert row.period_a.mean_pct == 50.0
    assert row.period_a.sigma_pct == 0.0
    assert row.period_a.n_days == 2
    assert row.p_value == 1.0


def test_compare_two_periods_significant():
    matrix_a = _matrix([_day(f"2025-07-{i:02d}", 100, 50) for i in range(1, 11)])
    matrix_b = _matrix([_day(f"2025-08-{i:02d}", 100, 70) for i in range(1, 11)])
    report = compare_funnel_periods(
        matrix_a,
        matrix_b,
        baseline_chapter_order=2,
        skip_book_page=True,
    )
    row = next(r for r in report.rows if r.site_chapter_order == 3)
    assert row.period_a.mean_pct == 50.0
    assert row.period_b.mean_pct == 70.0
    assert row.mean_diff == 20.0
    assert row.p_value is not None
    assert row.p_value < 0.05


def test_insufficient_days_pvalue_none():
    matrix_a = _matrix([_day("2025-07-01", 100, 50)])
    matrix_b = _matrix([_day("2025-08-01", 100, 70)])
    report = compare_funnel_periods(
        matrix_a,
        matrix_b,
        baseline_chapter_order=2,
        skip_book_page=True,
    )
    row = next(r for r in report.rows if r.site_chapter_order == 3)
    assert row.period_a.n_days == 1
    assert row.p_value is None


def test_skip_zero_baseline_day():
    matrix = _matrix(
        [
            _day("2025-07-01", 0, 10),
            _day("2025-07-02", 100, 50),
        ]
    )
    report = compare_funnel_periods(
        matrix,
        matrix,
        baseline_chapter_order=2,
        skip_book_page=True,
    )
    row = next(r for r in report.rows if r.site_chapter_order == 3)
    assert row.period_a.n_days == 1
    assert row.period_a.mean_pct == 50.0


def test_daily_matrix_from_json(minimal_snapshot_path: Path):
    matrix = daily_matrix_from_json(minimal_snapshot_path)
    assert date(2025, 7, 1) in matrix
    assert matrix[date(2025, 7, 1)][2] == ("Глава 1", 80)


def test_compare_from_json_fixture(minimal_snapshot_path: Path):
    matrix = daily_matrix_from_json(minimal_snapshot_path)
    report = compare_funnel_periods(
        matrix,
        matrix,
        baseline_chapter_order=2,
        skip_book_page=True,
        book_id=1,
    )
    assert report.book_id == 1
    assert len(report.rows) >= 2


def test_missing_baseline_raises():
    matrix = _matrix([_day("2025-07-01", 100, 50)])
    with pytest.raises(ValueError, match="chapter_order=99"):
        compare_funnel_periods(
            matrix,
            matrix,
            baseline_chapter_order=99,
            skip_book_page=True,
        )


def test_save_compare_csv(tmp_path: Path, minimal_snapshot_path: Path):
    matrix = daily_matrix_from_json(minimal_snapshot_path)
    report = compare_funnel_periods(
        matrix,
        matrix,
        baseline_chapter_order=2,
        skip_book_page=True,
    )
    out = save_funnel_compare_csv(report, tmp_path / "cmp.csv")
    text = out.read_text(encoding="utf-8-sig")
    assert "μ_A" in text
    assert "p_value" in text
    assert "50,00" in text or "50,0" in text
