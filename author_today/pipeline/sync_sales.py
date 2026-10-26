"""Пайплайн загрузки продаж с merchant/dashboard."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from selenium.webdriver.remote.webdriver import WebDriver

from author_today.auth.base import AuthProvider
from author_today.browser.factory import create_driver
from author_today.domain.sales import SaleSnapshot
from author_today.fetch.sales_page import load_sale_events, sale_snapshot_from_events
from author_today.pipeline.sync_reads import _auth_provider
from author_today.storage.persist import persist_sale_snapshot
from config.settings import Settings, ensure_data_dirs


def _load_and_persist_sales_period(
    driver: WebDriver,
    auth: AuthProvider,
    settings: Settings,
    period_start: date,
    period_end: date,
    *,
    save_raw: bool,
    save_mssql: bool,
) -> SaleSnapshot:
    events = load_sale_events(
        driver,
        auth,
        settings.book_id,
        period_start,
        period_end,
    )
    snapshot = sale_snapshot_from_events(
        events,
        book_id=settings.book_id,
        period_start=period_start,
        period_end=period_end,
    )
    if save_raw or save_mssql:
        persist_sale_snapshot(
            snapshot,
            settings,
            save_raw=save_raw,
            save_mssql=save_mssql,
        )
    return snapshot


def sync_sales_by_period(
    settings: Settings,
    period_start: date,
    period_end: date,
    *,
    save_raw: bool = False,
    save_mssql: bool = True,
    device_code_provider: Callable[[str], str] | None = None,
    wait_login_seconds: int | None = None,
) -> SaleSnapshot:
    """Полный цикл: браузер → вход → getdetailstable → MS SQL."""
    if period_start > period_end:
        raise ValueError("Начало периода должно быть не позже конца.")
    ensure_data_dirs()
    auth = _auth_provider(
        settings,
        device_code_provider=device_code_provider,
        wait_login_seconds=wait_login_seconds,
    )
    driver = create_driver(settings)
    try:
        return _load_and_persist_sales_period(
            driver,
            auth,
            settings,
            period_start,
            period_end,
            save_raw=save_raw,
            save_mssql=save_mssql,
        )
    finally:
        driver.quit()
