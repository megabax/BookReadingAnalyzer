"""URL и параметры отчёта продаж author.today (merchant/dashboard)."""

from __future__ import annotations

from datetime import date, datetime, time
from urllib.parse import urlencode

DASHBOARD_BASE = "https://author.today/merchant/dashboard"
DETAILS_BASE = "https://author.today/merchant/getdetailstable"


def format_sales_period_bounds(period_start: date, period_end: date) -> tuple[str, str]:
    """Границы периода в формате query сайта (как у stats / merchant)."""
    start_dt = datetime.combine(period_start, time(20, 0))
    end_dt = datetime.combine(period_end, time(19, 59, 59, 999000))
    return (
        start_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        end_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
    )


def build_dashboard_url(
    book_id: int,
    period_start: date,
    period_end: date,
    *,
    group_by: str = "work",
) -> str:
    """Страница «Сводный отчет о продажах»."""
    start_s, end_s = format_sales_period_bounds(period_start, period_end)
    params = {
        "groupBy": group_by,
        "startDate": start_s,
        "endDate": end_s,
        "itemId": book_id,
    }
    return f"{DASHBOARD_BASE}?{urlencode(params)}"


def build_details_query(
    book_id: int,
    period_start: date,
    period_end: date,
    *,
    page: int = 1,
    page_size: int = 200,
    group_by: str = "work",
) -> dict[str, str | int]:
    """Параметры для /merchant/getdetailstable."""
    start_s, end_s = format_sales_period_bounds(period_start, period_end)
    return {
        "groupBy": group_by,
        "startDate": start_s,
        "endDate": end_s,
        "itemId": book_id,
        "page": page,
        "pageSize": page_size,
        "sort": "ProcessedTime-desc",
    }
