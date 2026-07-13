#!/usr/bin/env python
"""Удаление загрузок из MS SQL по book_id и fetched_at или period_start/period_end."""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from author_today.storage.mssql_repo import create_mssql_repository
from config.settings import Settings


def _parse_fetched_at(raw_value: str) -> datetime:
    normalized = raw_value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(
            "Неверный формат даты. Используйте YYYY-MM-DDTHH:MM:SS (или с миллисекундами)."
        ) from exc


def _parse_period_date(raw_value: str) -> date:
    try:
        return date.fromisoformat(raw_value)
    except ValueError as exc:
        raise ValueError(
            "Неверный формат даты периода. Используйте YYYY-MM-DD."
        ) from exc


def _resolve_book_id(args: argparse.Namespace) -> int:
    if args.book_id is not None and args.work_id is not None and args.book_id != args.work_id:
        raise SystemExit("Ошибка: --book-id и --work-id задают разные значения")
    book_id = args.book_id if args.book_id is not None else args.work_id
    if book_id is None:
        raise SystemExit("Ошибка: укажите --book-id")
    if args.work_id is not None and args.book_id is None:
        print(
            "Предупреждение: --work-id устарел, используйте --book-id",
            file=sys.stderr,
        )
    return book_id


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Удалить записи из chapter_reads и fetch_runs по book_id. "
            "Фильтр: время загрузки (fetched_at) или заявленный период (period_start/period_end)."
        )
    )
    parser.add_argument("--book-id", type=int, help="ID книги на author.today")
    parser.add_argument(
        "--work-id",
        type=int,
        help="(устар.) то же, что --book-id",
    )
    parser.add_argument(
        "--filter",
        choices=["fetched-at", "period"],
        default="fetched-at",
        help="Критерий отбора run'ов (по умолчанию fetched-at)",
    )
    parser.add_argument(
        "--fetched-from",
        type=str,
        help="Начало диапазона fetched_at (ISO), например 2026-06-02T09:12:33.123",
    )
    parser.add_argument(
        "--fetched-to",
        type=str,
        help="Конец диапазона fetched_at (ISO), например 2026-06-02T10:00:00",
    )
    parser.add_argument(
        "--period-start",
        type=str,
        help="Начало заявленного периода загрузки (YYYY-MM-DD), как в fetch_runs.period_start",
    )
    parser.add_argument(
        "--period-end",
        type=str,
        help="Конец заявленного периода загрузки (YYYY-MM-DD), как в fetch_runs.period_end",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только показать, сколько будет удалено",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Не спрашивать подтверждение",
    )
    args = parser.parse_args()
    book_id = _resolve_book_id(args)

    settings = Settings.from_env()
    if not settings.has_mssql():
        print("Ошибка: MS SQL не настроен в .env", file=sys.stderr)
        return 1

    repo = create_mssql_repository(settings)

    try:
        if args.filter == "fetched-at":
            if not args.fetched_from or not args.fetched_to:
                raise ValueError("Для --filter fetched-at укажите --fetched-from и --fetched-to")
            fetched_from = _parse_fetched_at(args.fetched_from)
            fetched_to = _parse_fetched_at(args.fetched_to)
            if fetched_from > fetched_to:
                raise ValueError("--fetched-from должен быть меньше или равен --fetched-to")
            preview = repo.preview_delete_runs_by_fetched_at(book_id, fetched_from, fetched_to)
            filter_desc = (
                f"fetched_at от {args.fetched_from} до {args.fetched_to}"
            )
            delete = lambda: repo.delete_runs_by_fetched_at(book_id, fetched_from, fetched_to)
        else:
            if not args.period_start or not args.period_end:
                raise ValueError("Для --filter period укажите --period-start и --period-end")
            period_start = _parse_period_date(args.period_start)
            period_end = _parse_period_date(args.period_end)
            if period_start > period_end:
                raise ValueError("--period-start должен быть не позже --period-end")
            preview = repo.preview_delete_runs_by_period(book_id, period_start, period_end)
            filter_desc = f"period {period_start} .. {period_end}"
            delete = lambda: repo.delete_runs_by_period(book_id, period_start, period_end)
    except ValueError as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 1

    print(f"Фильтр: book_id={book_id}, {filter_desc}")
    if preview.run_ids:
        print("Найденные run_id: " + ", ".join(str(v) for v in preview.run_ids))
    print(f"Найдено fetch_runs: {preview.runs_count}")
    print(f"Найдено chapter_reads: {preview.reads_count}")

    if args.dry_run:
        return 0

    if preview.runs_count == 0:
        print("Нечего удалять.")
        return 0

    if not args.yes:
        answer = input("Удалить найденные записи? [y/N]: ").strip().lower()
        if answer not in ("y", "yes", "д", "да"):
            print("Отменено.")
            return 0

    result = delete()
    print(f"Удалено chapter_reads: {result.deleted_reads}")
    print(f"Удалено fetch_runs: {result.deleted_runs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
