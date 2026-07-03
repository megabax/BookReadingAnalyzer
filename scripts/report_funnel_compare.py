#!/usr/bin/env python
"""Сравнение двух воронок одной книги за разные периоды."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from author_today.analyze.funnel_compare import (
    compare_funnel_periods,
    daily_matrix_from_json,
    daily_matrix_from_mssql,
    print_funnel_compare,
    save_funnel_compare_csv,
)
from config.settings import Settings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Сравнение воронок: дневные %% от базовой главы, μ, σ, p-value"
    )
    parser.add_argument("--book-id", type=int, help="ID книги (AT_BOOK_ID / AT_WORK_ID)")
    parser.add_argument("--start-a", type=str, required=True, help="Период A: начало YYYY-MM-DD")
    parser.add_argument("--end-a", type=str, required=True, help="Период A: конец YYYY-MM-DD")
    parser.add_argument("--start-b", type=str, required=True, help="Период B: начало YYYY-MM-DD")
    parser.add_argument("--end-b", type=str, required=True, help="Период B: конец YYYY-MM-DD")
    parser.add_argument(
        "--base-order",
        type=int,
        required=True,
        help="chapter_order базовой главы (100%% для дневных долей)",
    )
    parser.add_argument(
        "--skip-book-page",
        action="store_true",
        help="Не включать «Страница книги»",
    )
    parser.add_argument(
        "--json-a",
        type=Path,
        help="(устарело) период A из JSON; только с AT_ENABLE_LEGACY_JSON=yes",
    )
    parser.add_argument(
        "--json-b",
        type=Path,
        help="(устарело) период B из JSON; только с AT_ENABLE_LEGACY_JSON=yes",
    )
    parser.add_argument(
        "--csv",
        nargs="?",
        const=Path(""),
        default=None,
        type=Path,
        metavar="PATH",
        help="Сохранить сводку в CSV",
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    book_id = args.book_id if args.book_id is not None else settings.book_id
    period_a_start = date.fromisoformat(args.start_a)
    period_a_end = date.fromisoformat(args.end_a)
    period_b_start = date.fromisoformat(args.start_b)
    period_b_end = date.fromisoformat(args.end_b)

    try:
        if args.json_a and args.json_b:
            if not settings.enable_legacy_json:
                print(
                    "Ошибка: --json-a/--json-b отключены (источник правды — MS SQL). "
                    "Для отладки: AT_ENABLE_LEGACY_JSON=yes",
                    file=sys.stderr,
                )
                return 1
            matrix_a = daily_matrix_from_json(args.json_a)
            matrix_b = daily_matrix_from_json(args.json_b)
        elif args.json_a or args.json_b:
            print("Ошибка: укажите оба --json-a и --json-b", file=sys.stderr)
            return 1
        elif settings.has_mssql():
            matrix_a = daily_matrix_from_mssql(
                settings, book_id, period_a_start, period_a_end
            )
            matrix_b = daily_matrix_from_mssql(
                settings, book_id, period_b_start, period_b_end
            )
        else:
            print(
                "Ошибка: настройте MS SQL в .env (источник данных для отчётов)",
                file=sys.stderr,
            )
            return 1

        report = compare_funnel_periods(
            matrix_a,
            matrix_b,
            baseline_chapter_order=args.base_order,
            skip_book_page=args.skip_book_page,
            book_id=book_id,
            period_a_start=period_a_start,
            period_a_end=period_a_end,
            period_b_start=period_b_start,
            period_b_end=period_b_end,
        )
        print_funnel_compare(report)
    except ValueError as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 1

    if args.csv is not None:
        if args.csv.name:
            csv_path = args.csv
        else:
            csv_path = Path("data/reports") / (
                f"funnel_compare_{book_id}_"
                f"{period_a_start:%Y%m%d}_{period_a_end:%Y%m%d}_vs_"
                f"{period_b_start:%Y%m%d}_{period_b_end:%Y%m%d}.csv"
            )
        saved = save_funnel_compare_csv(report, csv_path)
        print(f"CSV: {saved}")

    return 0


if __name__ == "__main__":
    from author_today.cli_reminders import run_with_manual_smoke_reminder

    sys.exit(run_with_manual_smoke_reminder(main))
