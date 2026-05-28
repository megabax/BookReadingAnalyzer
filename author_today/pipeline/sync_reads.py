from __future__ import annotations

from datetime import date
from pathlib import Path

from selenium.common.exceptions import TimeoutException

from author_today.auth.manual import ManualAuthProvider
from author_today.auth.selenium_login import SeleniumLoginProvider
from author_today.browser.factory import create_driver
from author_today.domain.models import StatsTable
from author_today.fetch.stats_page import load_stats_table
from author_today.fetch.stats_url import build_stats_url
from author_today.storage.export import save_csv, save_json
from author_today.storage.persist import persist_snapshot, snapshot_from_table
from config.settings import Settings, ensure_data_dirs


def _auth_provider(settings: Settings):
    if settings.has_auto_login():
        return SeleniumLoginProvider(
            settings.at_email,
            settings.at_password,
            auth_timeout=settings.auth_timeout,
        )
    return ManualAuthProvider(settings.wait_login_seconds)


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
    Возвращает таблицу; при save_raw сохраняет JSON в data/raw/.
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
) -> StatsTable:
    url = build_stats_url(
        settings.book_id,
        period_start,
        period_end,
        value_type=settings.value_type,
    )
    table = sync_reads(
        url,
        settings,
        period_start=period_start,
        period_end=period_end,
        save_raw=save_raw,
        save_mssql=save_mssql,
    )
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
