#!/usr/bin/env python
"""Проверка загрузок в MS SQL на пропуски дней внутри заявленного периода."""

#!/usr/bin/env python
"""Проверка загрузок в MS SQL на пропуски дней внутри заявленного периода.

Требуется editable-установка: pip install -e .
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from author_today.storage.load_gaps import (
    RunGapReport,
    find_missing_days,
    format_date_ranges,
    iter_period_days,
)
from author_today.storage.mssql_repo import RunDateCoverage, create_mssql_repository
from config.settings import Settings


def _expected_day_count(period_start: date, period_end: date) -> int:
    return sum(1 for _ in iter_period_days(period_start, period_end))


def _build_reports(coverage: list[RunDateCoverage]) -> list[RunGapReport]:
    reports: list[RunGapReport] = []
    for run in coverage:
        missing = find_missing_days(run.period_start, run.period_end, set(run.read_dates))
        reports.append(
            RunGapReport(
                run_id=run.run_id,
                book_id=run.book_id,
                book_title=run.book_title,
                period_start=run.period_start,
                period_end=run.period_end,
                fetched_at=run.fetched_at.isoformat(sep=" ", timespec="seconds"),
                expected_days=_expected_day_count(run.period_start, run.period_end),
                actual_days=len(run.read_dates),
                missing_days=tuple(missing),
            )
        )
    return reports


def _print_text(reports: list[RunGapReport], *, only_gaps: bool) -> None:
    if not reports:
        print("Загрузок в БД не найдено.")
        return

    shown = [r for r in reports if r.has_gaps] if only_gaps else reports
    if only_gaps and not shown:
        print(f"Проверено run'ов: {len(reports)}. Пропусков нет.")
        return

    for report in shown:
        title = f" ({report.book_title})" if report.book_title else ""
        status = "ПРОПУСКИ" if report.has_gaps else "OK"
        print(
            f"[{status}] book_id={report.book_id}{title}, run_id={report.run_id}, "
            f"период {report.period_start} .. {report.period_end}, "
            f"fetched_at={report.fetched_at}"
        )
        print(
            f"  дней: ожидалось {report.expected_days}, "
            f"в БД {report.actual_days}, пропущено {len(report.missing_days)}"
        )
        if report.has_gaps:
            print(f"  пропуски: {format_date_ranges(report.missing_days)}")
        print()


def _print_json(reports: list[RunGapReport]) -> None:
    payload = [
        {
            "run_id": r.run_id,
            "book_id": r.book_id,
            "book_title": r.book_title,
            "period_start": r.period_start.isoformat(),
            "period_end": r.period_end.isoformat(),
            "fetched_at": r.fetched_at,
            "expected_days": r.expected_days,
            "actual_days": r.actual_days,
            "missing_days": [d.isoformat() for d in r.missing_days],
            "missing_ranges": format_date_ranges(r.missing_days),
            "has_gaps": r.has_gaps,
        }
        for r in reports
    ]
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Проверить fetch_runs в MS SQL: для каждой загрузки сравнить "
            "заявленный период (period_start..period_end) с фактическими read_date."
        )
    )
    parser.add_argument("--book-id", type=int, help="Только указанная книга")
    parser.add_argument(
        "--only-gaps",
        action="store_true",
        help="Показать только run'ы с пропусками (в текстовом режиме)",
    )
    parser.add_argument("--json", action="store_true", help="Вывод в JSON")
    args = parser.parse_args()

    settings = Settings.from_env()
    if not settings.has_mssql():
        print("Ошибка: MS SQL не настроен в .env", file=sys.stderr)
        return 1

    repo = create_mssql_repository(settings)
    coverage = repo.list_run_date_coverage(book_id=args.book_id)
    reports = _build_reports(coverage)

    if args.json:
        _print_json(reports)
    else:
        _print_text(reports, only_gaps=args.only_gaps)
        gap_count = sum(1 for r in reports if r.has_gaps)
        if reports and not args.only_gaps:
            print(f"Итого: run'ов {len(reports)}, с пропусками {gap_count}.")

    return 1 if any(r.has_gaps for r in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
