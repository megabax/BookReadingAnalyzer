"""Загрузка продаж: Selenium auth → HTTP getdetailstable."""

from __future__ import annotations

from datetime import date, datetime

from selenium.webdriver.remote.webdriver import WebDriver

from author_today.auth.base import AuthProvider
from author_today.domain.sales import SaleEvent, SaleSnapshot
from author_today.fetch.sales_client import fetch_sale_events, session_from_driver
from author_today.fetch.sales_url import build_dashboard_url


def load_sale_events(
    driver: WebDriver,
    auth: AuthProvider,
    book_id: int,
    period_start: date,
    period_end: date,
    *,
    page_size: int = 200,
) -> list[SaleEvent]:
    """
    Открыть dashboard (логин при необходимости), затем скачать все строки продаж.
    """
    url = build_dashboard_url(book_id, period_start, period_end)
    driver.get(url)
    auth.ensure_logged_in(driver)
    # После логина могли уйти на /account/login — вернуться к отчёту.
    if "/merchant/dashboard" not in (driver.current_url or ""):
        driver.get(url)

    session = session_from_driver(driver)
    return fetch_sale_events(
        session,
        book_id,
        period_start,
        period_end,
        page_size=page_size,
    )


def sale_snapshot_from_events(
    events: list[SaleEvent],
    *,
    book_id: int,
    period_start: date,
    period_end: date,
    fetched_at: datetime | None = None,
) -> SaleSnapshot:
    return SaleSnapshot(
        book_id=book_id,
        period_start=period_start,
        period_end=period_end,
        fetched_at=fetched_at or datetime.now(),
        events=tuple(events),
    )
