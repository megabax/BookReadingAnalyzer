"""Отчёты для Streamlit UI — вызовы analyze без subprocess и без SQL в UI.

Источник данных для отчётов — MS SQL. JSON в data/raw — устаревший промежуточный формат.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from author_today.analyze.funnel import FunnelStep, funnel_from_snapshot
from author_today.analyze.funnel_compare import (
    FunnelCompareReport,
    compare_funnel_periods,
    daily_matrix_from_snapshot,
)
from author_today.domain.models import ReadSnapshot
from author_today.storage.mssql_repo import create_mssql_repository
from config.settings import RAW_DIR, Settings


def list_raw_snapshots(*, book_id: int | None = None) -> list[Path]:
    """Устаревшие JSON-снимки в data/raw (только при AT_ENABLE_LEGACY_JSON=yes)."""
    if not RAW_DIR.is_dir():
        return []
    paths = sorted(RAW_DIR.glob("reads_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if book_id is None:
        return paths
    prefix = f"reads_{book_id}_"
    return [p for p in paths if p.name.startswith(prefix)]


def _require_mssql(settings: Settings) -> None:
    if not settings.has_mssql():
        raise RuntimeError(
            "Отчёты строятся из MS SQL. Настройте MSSQL_* или MSSQL_CONNECTION_STRING в .env"
        )


def load_read_snapshot(
    settings: Settings,
    book_id: int,
    period_start: date,
    period_end: date,
) -> ReadSnapshot:
    _require_mssql(settings)
    return create_mssql_repository(settings).load_snapshot(
        book_id, period_start, period_end
    )


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
        if not settings.enable_legacy_json:
            raise RuntimeError(
                "JSON отключён (источник правды — MS SQL). "
                "Для отладки задайте AT_ENABLE_LEGACY_JSON=yes"
            )
        snapshot = ReadSnapshot.from_json(json_path)
    else:
        snapshot = load_read_snapshot(settings, book_id, period_start, period_end)
    return funnel_from_snapshot(
        snapshot,
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
    if json_path_a or json_path_b:
        if not settings.enable_legacy_json:
            raise RuntimeError(
                "JSON отключён (источник правды — MS SQL). "
                "Для отладки задайте AT_ENABLE_LEGACY_JSON=yes"
            )
        if not (json_path_a and json_path_b):
            raise RuntimeError("Укажите оба json_path_a и json_path_b")
        matrix_a = daily_matrix_from_snapshot(ReadSnapshot.from_json(json_path_a))
        matrix_b = daily_matrix_from_snapshot(ReadSnapshot.from_json(json_path_b))
    else:
        matrix_a = daily_matrix_from_snapshot(
            load_read_snapshot(settings, book_id, period_a_start, period_a_end)
        )
        matrix_b = daily_matrix_from_snapshot(
            load_read_snapshot(settings, book_id, period_b_start, period_b_end)
        )

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
