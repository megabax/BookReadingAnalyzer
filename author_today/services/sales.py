"""Сервис просмотра загруженных продаж."""

from __future__ import annotations

from datetime import date

from author_today.errors import ConfigError
from author_today.storage.factory import get_repository
from author_today.storage.mssql_repo import (
    SaleEventRow,
    SaleLoadInfo,
    SalesPeriodReport,
)
from config.settings import Settings

WORK_FORMAT_LABELS = {
    1: "Электронная книга",
    2: "Аудиокнига",
}


def work_format_label(work_format: int | None) -> str:
    if work_format is None:
        return "—"
    return WORK_FORMAT_LABELS.get(work_format, str(work_format))


def load_sale_load_info(
    settings: Settings,
    book_id: int,
    *,
    limit: int = 50,
) -> SaleLoadInfo | None:
    if not settings.has_mssql():
        return None
    return get_repository(settings).get_sale_load_info(book_id, limit=limit)


def list_sale_events_for_run(
    settings: Settings,
    book_id: int,
    run_id: int,
) -> list[SaleEventRow]:
    if not settings.has_mssql():
        raise ConfigError("MS SQL не настроен.")
    return get_repository(settings).list_sale_events_for_run(book_id, run_id)


def load_sales_period_report(
    settings: Settings,
    book_id: int,
    period_start: date,
    period_end: date,
) -> SalesPeriodReport:
    if not settings.has_mssql():
        raise ConfigError("MS SQL не настроен.")
    if period_start > period_end:
        raise ValueError("Начало периода не может быть позже конца.")
    return get_repository(settings).load_sales_period_report(
        book_id, period_start, period_end
    )
