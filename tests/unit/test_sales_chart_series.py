"""Группировка графика продаж с нулевыми бакетами."""

from __future__ import annotations

from datetime import date, datetime

from author_today.services.sales import build_sales_chart_series
from author_today.storage.mssql_repo import SaleEventRow, SalesPeriodReport


def _event(day: date, *, income: float = 100.0, price: float = 140.0) -> SaleEventRow:
    return SaleEventRow(
        event_id=1,
        run_id=1,
        processed_at=datetime(day.year, day.month, day.day, 12, 0),
        book_id=1,
        work_format=1,
        price=price,
        commission=0.3,
        author_income=income,
    )


def _report(
    start: date,
    end: date,
    events: list[SaleEventRow],
) -> SalesPeriodReport:
    return SalesPeriodReport(
        book_id=1,
        period_start=start,
        period_end=end,
        events=tuple(events),
        daily=(),
        sales_count=len(events),
        income_sum=sum(e.author_income for e in events),
        price_sum=sum(e.price for e in events),
    )


def test_day_series_fills_zeros():
    report = _report(
        date(2026, 10, 1),
        date(2026, 10, 3),
        [_event(date(2026, 10, 2), income=50.0)],
    )
    points = build_sales_chart_series(report, group_by="day")
    assert [p.label for p in points] == ["2026-10-01", "2026-10-02", "2026-10-03"]
    assert [p.sales_count for p in points] == [0, 1, 0]
    assert points[1].income_sum == 50.0
    assert points[0].income_sum == 0.0


def test_week_series_covers_period():
    # Mon 2026-09-28 .. Sun 2026-10-11 → two ISO weeks
    report = _report(
        date(2026, 10, 1),
        date(2026, 10, 10),
        [_event(date(2026, 10, 2))],
    )
    points = build_sales_chart_series(report, group_by="week")
    assert len(points) == 2
    assert points[0].sales_count == 1
    assert points[1].sales_count == 0


def test_month_series_fills_empty_months():
    report = _report(
        date(2026, 9, 15),
        date(2026, 11, 5),
        [_event(date(2026, 10, 20))],
    )
    points = build_sales_chart_series(report, group_by="month")
    assert [p.label for p in points] == ["2026-09", "2026-10", "2026-11"]
    assert [p.sales_count for p in points] == [0, 1, 0]


def test_empty_events_still_shows_zero_buckets():
    report = _report(date(2026, 10, 1), date(2026, 10, 2), [])
    points = build_sales_chart_series(report, group_by="day")
    assert len(points) == 2
    assert all(p.sales_count == 0 for p in points)
