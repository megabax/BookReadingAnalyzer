#!/usr/bin/env python
"""Загрузка продаж книги с author.today. Запуск: python scripts/fetch_sales.py

Требуется editable-установка: pip install -e .
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from selenium.common.exceptions import TimeoutException

from author_today.cli_reminders import run_with_manual_smoke_reminder
from author_today.errors import AuthorTodayError
from author_today.pipeline.sync_sales import sync_sales_by_period
from config.settings import Settings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Продажи author.today (/merchant/getdetailstable)"
    )
    parser.add_argument("--book-id", type=int, help="ID книги (workId / itemId)")
    parser.add_argument("--start", type=str, help="Начало периода YYYY-MM-DD")
    parser.add_argument("--end", type=str, help="Конец периода YYYY-MM-DD")
    parser.add_argument(
        "--wait-login",
        type=int,
        metavar="SEC",
        help="Пауза для ручного входа (перекрывает AT_WAIT_LOGIN)",
    )
    parser.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Headless Chrome (по умолчанию из AT_HEADLESS).",
    )
    parser.add_argument("--user-data-dir", help="Профиль Chrome")
    parser.add_argument("--no-raw", action="store_true", help="Не писать JSON в data/raw")
    parser.add_argument("--no-mssql", action="store_true", help="Не сохранять в MS SQL")
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Сохранить JSON снимка в data/raw (по умолчанию выкл.)",
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    if args.book_id is not None:
        settings.book_id = args.book_id
    if args.wait_login is not None:
        settings.wait_login_seconds = args.wait_login
    if args.headless is not None:
        settings.headless = args.headless
    if args.user_data_dir:
        settings.chrome_user_data_dir = args.user_data_dir

    period_start = (
        date.fromisoformat(args.start) if args.start else settings.default_period_start
    )
    period_end = (
        date.fromisoformat(args.end) if args.end else settings.default_period_end
    )
    save_mssql = not args.no_mssql
    save_raw = bool(args.raw) and not args.no_raw

    print(f"book_id={settings.book_id} · {period_start} — {period_end}")
    print(f"Браузер: {'headless' if settings.headless else 'с окном Chrome'}")
    if settings.has_auto_login():
        print("Авторизация: автоматически (AT_EMAIL / AT_PASSWORD)")
    else:
        print(f"Авторизация: ручная пауза {settings.wait_login_seconds} с")

    try:
        snap = sync_sales_by_period(
            settings,
            period_start,
            period_end,
            save_raw=save_raw,
            save_mssql=save_mssql,
        )
        print(f"Готово: продаж={len(snap.events)}")
        return 0
    except AuthorTodayError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        if not settings.headless:
            print("Браузер: пауза 30 с для проверки...", file=sys.stderr)
            time.sleep(30)
        return 1
    except (TimeoutException, RuntimeError, ValueError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        if not settings.headless:
            print("Браузер: пауза 30 с для проверки...", file=sys.stderr)
            time.sleep(30)
        return 1


if __name__ == "__main__":
    sys.exit(run_with_manual_smoke_reminder(main))
