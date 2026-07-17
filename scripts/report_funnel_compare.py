#!/usr/bin/env python
"""Сравнение двух воронок одной книги за разные периоды.

Требуется editable-установка: pip install -e .
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from author_today.analyze.funnel_compare import (
    compare_funnel_periods,
    daily_matrix_from_json,
    daily_matrix_from_mssql,
    print_funnel_compare,
    save_funnel_compare_csv,
)
from author_today.cli_common import (
    add_book_id_arg,
    add_csv_output_arg,
    add_funnel_filter_args,
    add_period_args,
    print_error,
    require_legacy_json,
    require_mssql,
    resolve_book_id,
)
from config.settings import Settings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Сравнение воронок: дневные %% от базовой главы, mu, sigma, p-value"
    )
    add_book_id_arg(parser)
    add_period_args(
        parser,
        start_dest="start_a",
        end_dest="end_a",
        start_option="--start-a",
        end_option="--end-a",
        start_help="Период A: начало YYYY-MM-DD",
        end_help="Период A: конец YYYY-MM-DD",
        required=True,
    )
    add_period_args(
        parser,
        start_dest="start_b",
        end_dest="end_b",
        start_option="--start-b",
        end_option="--end-b",
        start_help="Период B: начало YYYY-MM-DD",
        end_help="Период B: конец YYYY-MM-DD",
        required=True,
    )
    add_funnel_filter_args(
        parser,
        base_order_required=True,
        skip_book_page_help="Не включать «Страница книги»",
        base_order_help="chapter_order базовой главы (100%% для дневных долей)",
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
    add_csv_output_arg(parser, help="Сохранить сводку в CSV")
    args = parser.parse_args()

    settings = Settings.from_env()
    book_id = resolve_book_id(args, settings)
    period_a_start = date.fromisoformat(args.start_a)
    period_a_end = date.fromisoformat(args.end_a)
    period_b_start = date.fromisoformat(args.start_b)
    period_b_end = date.fromisoformat(args.end_b)

    try:
        if args.json_a and args.json_b:
            if not require_legacy_json(settings, flags="--json-a/--json-b"):
                return 1
            matrix_a = daily_matrix_from_json(args.json_a)
            matrix_b = daily_matrix_from_json(args.json_b)
        elif args.json_a or args.json_b:
            print_error("укажите оба --json-a и --json-b")
            return 1
        elif require_mssql(settings):
            matrix_a = daily_matrix_from_mssql(
                settings, book_id, period_a_start, period_a_end
            )
            matrix_b = daily_matrix_from_mssql(
                settings, book_id, period_b_start, period_b_end
            )
        else:
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
        print_error(e)
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
