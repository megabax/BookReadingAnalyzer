from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from selenium.common.exceptions import TimeoutException

from author_today.analyze.reads import summary_from_table
from author_today.auth.manual import ManualAuthProvider
from author_today.auth.selenium_login import SeleniumLoginProvider
from author_today.browser.factory import create_driver
from author_today.domain.models import ReadSnapshot, StatsTable
from author_today.fetch.stats_page import load_stats_table
from author_today.fetch.stats_url import build_stats_url
from author_today.storage.export import (
    print_table,
    save_csv,
    save_json,
    save_snapshot_raw,
)
from config.settings import RAW_DIR, Settings, ensure_data_dirs


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
        print_table(table)
        print(summary_from_table(table))

        if save_raw and period_start and period_end:
            snapshot = ReadSnapshot.from_stats_table(
                table,
                work_id=settings.work_id,
                period_start=period_start,
                period_end=period_end,
            )
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            raw_path = RAW_DIR / f"reads_{settings.work_id}_{stamp}.json"
            save_snapshot_raw(snapshot, raw_path)
            print(f"Снимок: {raw_path}")

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
) -> StatsTable:
    url = build_stats_url(
        settings.work_id,
        period_start,
        period_end,
        value_type=settings.value_type,
    )
    print(f"URL: {url}")
    table = sync_reads(
        url,
        settings,
        period_start=period_start,
        period_end=period_end,
    )
    if output_csv:
        save_csv(table, output_csv)
        print(f"CSV: {output_csv}")
    if output_json:
        save_json(
            table,
            output_json,
            work_id=settings.work_id,
            period_start=period_start,
            period_end=period_end,
        )
        print(f"JSON: {output_json}")
    return table
