"""CLI проекта (логика бывшего selenium_stats.py)."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path

from selenium.common.exceptions import TimeoutException

from author_today.pipeline.sync_reads import sync_reads, sync_reads_by_period
from config.settings import Settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Статистика прочтений author.today")
    parser.add_argument(
        "url",
        nargs="?",
        help="URL страницы; если не указан — используется URL по умолчанию из config",
    )
    parser.add_argument("--work-id", type=int, help="ID книги на author.today")
    parser.add_argument("--start", type=str, help="Начало периода YYYY-MM-DD")
    parser.add_argument("--end", type=str, help="Конец периода YYYY-MM-DD")
    parser.add_argument(
        "--wait-login",
        type=int,
        metavar="SEC",
        help="Пауза для ручного входа (перекрывает AT_WAIT_LOGIN)",
    )
    parser.add_argument("--timeout", type=int, help="Таймаут ожидания таблицы")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--user-data-dir", help="Профиль Chrome")
    parser.add_argument("-o", "--output", type=Path, help="Сохранить CSV")
    parser.add_argument("--json", type=Path, help="Сохранить JSON")
    parser.add_argument("--no-raw", action="store_true", help="Не сохранять снимок в data/raw")
    args = parser.parse_args()

    settings = Settings.from_env()
    if settings.has_auto_login():
        print("Авторизация: автоматически (AT_EMAIL / AT_PASSWORD из .env)")
    elif settings.wait_login_seconds:
        print(f"Авторизация: ручная пауза {settings.wait_login_seconds} с")
    else:
        print("Авторизация: без .env — укажите --wait-login или AT_EMAIL/AT_PASSWORD")

    if args.work_id is not None:
        settings.work_id = args.work_id
    if args.wait_login is not None:
        settings.wait_login_seconds = args.wait_login
    if args.timeout is not None:
        settings.page_timeout = args.timeout
    if args.headless:
        settings.headless = True
    if args.user_data_dir:
        settings.chrome_user_data_dir = args.user_data_dir

    try:
        if args.url:
            table = sync_reads(
                args.url,
                settings,
                save_raw=not args.no_raw,
            )
            if args.output:
                from author_today.storage.export import save_csv

                save_csv(table, args.output)
            if args.json:
                from author_today.storage.export import save_json

                save_json(table, args.json)
        elif args.start and args.end:
            sync_reads_by_period(
                settings,
                date.fromisoformat(args.start),
                date.fromisoformat(args.end),
                output_csv=args.output,
                output_json=args.json,
            )
        else:
            url = settings.default_stats_url
            print(f"URL (по умолчанию): {url}")
            table = sync_reads(
                url,
                settings,
                period_start=settings.default_period_start,
                period_end=settings.default_period_end,
                save_raw=not args.no_raw,
            )
            if args.output:
                from author_today.storage.export import save_csv

                save_csv(table, args.output)
            if args.json:
                from author_today.storage.export import save_json

                save_json(table, args.json)
        return 0
    except (TimeoutException, RuntimeError, NotImplementedError) as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        if not settings.headless:
            print("Браузер: пауза 30 с для проверки...", file=sys.stderr)
            time.sleep(30)
        return 1


if __name__ == "__main__":
    sys.exit(main())
