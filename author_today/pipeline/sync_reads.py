from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.remote.webdriver import WebDriver

from author_today.auth.base import AuthProvider
from author_today.auth.manual import ManualAuthProvider
from author_today.auth.selenium_login import SeleniumLoginProvider
from author_today.browser.factory import create_driver
from author_today.domain.models import StatsTable
from author_today.fetch.periods import needs_monthly_chunks, split_period_into_months
from author_today.fetch.stats_page import load_stats_table
from author_today.fetch.stats_url import build_stats_url
from author_today.storage.export import save_csv, save_json
from author_today.storage.persist import persist_snapshot, snapshot_from_table
from config.settings import Settings, ensure_data_dirs


def _auth_provider(
    settings: Settings,
    *,
    device_code_provider: Callable[[str], str] | None = None,
    wait_login_seconds: int | None = None,
) -> AuthProvider:
    if settings.has_auto_login():
        return SeleniumLoginProvider(
            settings.at_email,
            settings.at_password,
            auth_timeout=settings.auth_timeout,
            code_provider=device_code_provider,
        )
    return ManualAuthProvider(
        wait_login_seconds
        if wait_login_seconds is not None
        else settings.wait_login_seconds
    )


def _load_and_persist_period(
    driver: WebDriver,
    auth: AuthProvider,
    settings: Settings,
    period_start: date,
    period_end: date,
    *,
    save_raw: bool,
    save_mssql: bool,
) -> StatsTable:
    url = build_stats_url(
        settings.book_id,
        period_start,
        period_end,
        value_type=settings.value_type,
    )
    table = load_stats_table(driver, url, auth, timeout=settings.page_timeout)
    if save_raw or save_mssql:
        snapshot = snapshot_from_table(table, settings, period_start, period_end)
        persist_snapshot(snapshot, settings, save_raw=save_raw, save_mssql=save_mssql)
    return table


def sync_reads(
    url: str,
    settings: Settings,
    *,
    period_start: date | None = None,
    period_end: date | None = None,
    save_raw: bool = True,
    save_mssql: bool = True,
) -> StatsTable:
    """
    Полный цикл: браузер → авторизация → загрузка страницы → парсинг.
    Для периода > 1 месяца используйте sync_reads_by_period.
    """
    ensure_data_dirs()
    auth = _auth_provider(settings)
    driver = create_driver(settings)

    try:
        table = load_stats_table(driver, url, auth, timeout=settings.page_timeout)

        if period_start and period_end and (save_raw or save_mssql):
            snapshot = snapshot_from_table(
                table, settings, period_start, period_end
            )
            persist_snapshot(
                snapshot,
                settings,
                save_raw=save_raw,
                save_mssql=save_mssql,
            )

        return table
    finally:
        driver.quit()


def sync_reads_by_period(
    settings: Settings,
    period_start: date,
    period_end: date,
    *,
    output_csv: Path | None = None,
    output_json: Path | None = None,
    save_raw: bool = True,
    save_mssql: bool = True,
    device_code_provider: Callable[[str], str] | None = None,
    wait_login_seconds: int | None = None,
) -> StatsTable:
    ensure_data_dirs()
    chunks = split_period_into_months(period_start, period_end)
    auth = _auth_provider(
        settings,
        device_code_provider=device_code_provider,
        wait_login_seconds=wait_login_seconds,
    )
    driver = create_driver(settings)

    try:
        if not needs_monthly_chunks(period_start, period_end):
            table = _load_and_persist_period(
                driver,
                auth,
                settings,
                period_start,
                period_end,
                save_raw=save_raw,
                save_mssql=save_mssql,
            )
        else:
            table: StatsTable | None = None
            for chunk_start, chunk_end in chunks:
                table = _load_and_persist_period(
                    driver,
                    auth,
                    settings,
                    chunk_start,
                    chunk_end,
                    save_raw=save_raw,
                    save_mssql=save_mssql,
                )
            print(
                f"Период {period_start} — {period_end}: "
                f"загружено порций по месяцам: {len(chunks)}"
            )
            if table is None:
                raise RuntimeError("Не удалось загрузить данные за период.")

        if output_csv:
            save_csv(table, output_csv)
        if output_json:
            save_json(
                table,
                output_json,
                book_id=settings.book_id,
                period_start=period_start,
                period_end=period_end,
            )
        return table
    finally:
        driver.quit()
