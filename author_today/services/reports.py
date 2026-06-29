"""Отчёты для Streamlit UI — вызовы analyze без subprocess и без SQL в UI."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from author_today.analyze.funnel import FunnelStep, funnel_from_json, funnel_from_mssql
from author_today.analyze.funnel_compare import (
    FunnelCompareReport,
    compare_funnel_periods,
    daily_matrix_from_json,
    daily_matrix_from_mssql,
)
from config.settings import RAW_DIR, Settings


def list_raw_snapshots(*, book_id: int | None = None) -> list[Path]:
    """JSON-снимки в data/raw (новые первыми)."""
    if not RAW_DIR.is_dir():
        return []
    paths = sorted(RAW_DIR.glob("reads_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if book_id is None:
        return paths
    prefix = f"reads_{book_id}_"
    return [p for p in paths if p.name.startswith(prefix)]


def load_funnel_steps(
    settings: Settings,
    book_id: int,
    period_start: date,
    period_end: date,
    *,
    json_path: Path | None = None,
    skip_book_page: bool = False,
    baseline_chapter_order: int | None = None,
) -> list[FunnelStep]:
    if json_path is not None:
        return funnel_from_json(
            json_path,
            skip_book_page=skip_book_page,
            baseline_chapter_order=baseline_chapter_order,
        )
    if not settings.has_mssql():
        raise RuntimeError("MS SQL не настроен. Укажите JSON или настройте .env")
    return funnel_from_mssql(
        settings,
        book_id,
        period_start,
        period_end,
        skip_book_page=skip_book_page,
        baseline_chapter_order=baseline_chapter_order,
    )


def load_funnel_compare(
    settings: Settings,
    book_id: int,
    period_a_start: date,
    period_a_end: date,
    period_b_start: date,
    period_b_end: date,
    *,
    json_path_a: Path | None = None,
    json_path_b: Path | None = None,
    baseline_chapter_order: int,
    skip_book_page: bool = False,
) -> FunnelCompareReport:
    if json_path_a and json_path_b:
        matrix_a = daily_matrix_from_json(json_path_a)
        matrix_b = daily_matrix_from_json(json_path_b)
    elif settings.has_mssql():
        matrix_a = daily_matrix_from_mssql(settings, book_id, period_a_start, period_a_end)
        matrix_b = daily_matrix_from_mssql(settings, book_id, period_b_start, period_b_end)
    else:
        raise RuntimeError("Укажите два JSON или настройте MS SQL в .env")

    return compare_funnel_periods(
        matrix_a,
        matrix_b,
        baseline_chapter_order=baseline_chapter_order,
        skip_book_page=skip_book_page,
        book_id=book_id,
        period_a_start=period_a_start,
        period_a_end=period_a_end,
        period_b_start=period_b_start,
        period_b_end=period_b_end,
    )
