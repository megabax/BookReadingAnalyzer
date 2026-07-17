#!/usr/bin/env python
"""Воронка прочтений по главам. Запуск: python scripts/report_funnel.py

Требуется editable-установка: pip install -e .
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from author_today.analyze.funnel import (
    default_funnel_csv_path,
    funnel_from_json,
    funnel_from_mssql,
    print_funnel,
    save_funnel_csv,
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
    parser = argparse.ArgumentParser(description="Воронка прочтений по порядку глав")
    add_book_id_arg(parser)
    add_period_args(parser)
    parser.add_argument(
        "--json",
        type=Path,
        help="(устарело) JSON из data/raw; только с AT_ENABLE_LEGACY_JSON=yes",
    )
    add_funnel_filter_args(parser)
    add_csv_output_arg(
        parser,
        options=("-o", "--output", "--csv"),
        help="Сохранить воронку в CSV (без PATH — data/reports/funnel_<book>_<start>_<end>.csv)",
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    book_id = resolve_book_id(args, settings)
    period_start = date.fromisoformat(args.start) if args.start else settings.default_period_start
    period_end = date.fromisoformat(args.end) if args.end else settings.default_period_end
    baseline = args.base_order

    try:
        if args.json:
            if not require_legacy_json(settings, flags="--json"):
                return 1
            json_data = json.loads(args.json.read_text(encoding="utf-8"))
            if args.book_id is None and json_data.get("book_id") is not None:
                book_id = int(json_data["book_id"])
            if not args.start and json_data.get("period_start"):
                period_start = date.fromisoformat(str(json_data["period_start"])[:10])
            if not args.end and json_data.get("period_end"):
                period_end = date.fromisoformat(str(json_data["period_end"])[:10])
            steps = funnel_from_json(
                args.json,
                skip_book_page=args.skip_book_page,
                baseline_chapter_order=baseline,
            )
            print_funnel(
                steps,
                book_id=book_id,
                period_start=period_start,
                period_end=period_end,
                title=f"Воронка (из файла {args.json.name})",
                baseline_chapter_order=baseline,
            )
        elif require_mssql(settings):
            steps = funnel_from_mssql(
                settings,
                book_id,
                period_start,
                period_end,
                skip_book_page=args.skip_book_page,
                baseline_chapter_order=baseline,
            )
            print_funnel(
                steps,
                book_id=book_id,
                period_start=period_start,
                period_end=period_end,
                baseline_chapter_order=baseline,
            )
        else:
            return 1
    except ValueError as e:
        print_error(e)
        return 1

    if args.csv is not None:
        csv_path = args.csv if args.csv.name else default_funnel_csv_path(
            book_id, period_start, period_end
        )
        saved = save_funnel_csv(steps, csv_path, baseline_chapter_order=baseline)
        print(f"CSV: {saved}")

    return 0


if __name__ == "__main__":
    from author_today.cli_reminders import run_with_manual_smoke_reminder

    sys.exit(run_with_manual_smoke_reminder(main))
