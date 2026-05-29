#!/usr/bin/env python
"""Воронка прочтений по главам. Запуск: python scripts/report_funnel.py"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from author_today.analyze.funnel import (
    funnel_from_json,
    funnel_from_mssql,
    print_funnel,
    save_funnel_csv,
)
from config.settings import Settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Воронка прочтений по порядку глав")
    parser.add_argument("--book-id", type=int, help="ID книги (AT_WORK_ID)")
    parser.add_argument("--start", type=str, help="Начало периода YYYY-MM-DD")
    parser.add_argument("--end", type=str, help="Конец периода YYYY-MM-DD")
    parser.add_argument("--json", type=Path, help="Взять данные из JSON (data/raw/...)")
    parser.add_argument(
        "--skip-book-page",
        action="store_true",
        help="Не включать «Страница книги» в воронку",
    )
    parser.add_argument("-o", "--output", type=Path, help="Сохранить CSV")
    args = parser.parse_args()

    settings = Settings.from_env()
    book_id = args.book_id if args.book_id is not None else settings.book_id
    period_start = date.fromisoformat(args.start) if args.start else settings.default_period_start
    period_end = date.fromisoformat(args.end) if args.end else settings.default_period_end

    if args.json:
        steps = funnel_from_json(args.json, skip_book_page=args.skip_book_page)
        print_funnel(
            steps,
            book_id=book_id,
            period_start=period_start,
            period_end=period_end,
            title=f"Воронка (из файла {args.json.name})",
        )
    elif settings.has_mssql():
        steps = funnel_from_mssql(
            settings,
            book_id,
            period_start,
            period_end,
            skip_book_page=args.skip_book_page,
        )
        print_funnel(steps, book_id=book_id, period_start=period_start, period_end=period_end)
    else:
        print(
            "Ошибка: укажите --json или настройте MS SQL в .env",
            file=sys.stderr,
        )
        return 1

    if args.output:
        save_funnel_csv(steps, args.output)
        print(f"CSV: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
