"""Сервис просмотра загруженных продаж."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

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

SalesGroupBy = Literal["day", "week", "month"]

SALES_GROUP_BY_LABELS: dict[SalesGroupBy, str] = {
    "day": "По дням",
    "week": "По неделям",
    "month": "По месяцам",
}


@dataclass(frozen=True)
class SalesChartPoint:
    """Точка графика (включая нулевые бакеты без продаж)."""

    label: str
    bucket_start: date
    sales_count: int
    income_sum: float
    price_sum: float


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


def _week_start(day: date) -> date:
    """Понедельник ISO-недели."""
    return day - timedelta(days=day.weekday())


def _month_start(day: date) -> date:
    return date(day.year, day.month, 1)


def _add_month(day: date) -> date:
    if day.month == 12:
        return date(day.year + 1, 1, 1)
    return date(day.year, day.month + 1, 1)


def _bucket_start(day: date, group_by: SalesGroupBy) -> date:
    if group_by == "day":
        return day
    if group_by == "week":
        return _week_start(day)
    return _month_start(day)


def _bucket_label(bucket_start: date, group_by: SalesGroupBy) -> str:
    if group_by == "day":
        return bucket_start.isoformat()
    if group_by == "week":
        iso_year, iso_week, _ = bucket_start.isocalendar()
        week_end = bucket_start + timedelta(days=6)
        return f"{iso_year}-W{iso_week:02d} ({bucket_start:%d.%m}–{week_end:%d.%m})"
    return f"{bucket_start.year}-{bucket_start.month:02d}"


def _iter_buckets(
    period_start: date,
    period_end: date,
    group_by: SalesGroupBy,
) -> list[date]:
    if period_start > period_end:
        return []
    start = _bucket_start(period_start, group_by)
    end = _bucket_start(period_end, group_by)
    buckets: list[date] = []
    current = start
    while current <= end:
        buckets.append(current)
        if group_by == "day":
            current = current + timedelta(days=1)
        elif group_by == "week":
            current = current + timedelta(days=7)
        else:
            current = _add_month(current)
    return buckets


def build_sales_chart_series(
    report: SalesPeriodReport,
    group_by: SalesGroupBy = "day",
) -> list[SalesChartPoint]:
    """
    Ряд для графика: все бакеты периода, пустые дни/недели/месяцы — с нулями.
    """
    if group_by not in SALES_GROUP_BY_LABELS:
        raise ValueError(f"Неизвестная группировка: {group_by!r}")

    totals: dict[date, list[float]] = {}
    for event in report.events:
        key = _bucket_start(event.processed_at.date(), group_by)
        slot = totals.setdefault(key, [0.0, 0.0, 0.0])
        slot[0] += 1
        slot[1] += event.author_income
        slot[2] += event.price

    points: list[SalesChartPoint] = []
    for bucket in _iter_buckets(report.period_start, report.period_end, group_by):
        count, income, price = totals.get(bucket, [0.0, 0.0, 0.0])
        points.append(
            SalesChartPoint(
                label=_bucket_label(bucket, group_by),
                bucket_start=bucket,
                sales_count=int(count),
                income_sum=float(income),
                price_sum=float(price),
            )
        )
    return points
