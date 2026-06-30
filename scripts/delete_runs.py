#!/usr/bin/env python
"""Удаление загрузок из MS SQL по book_id и диапазону fetched_at."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

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
        description="Удалить записи из chapter_reads и fetch_runs по book_id и диапазону fetched_at."
    )
    parser.add_argument("--book-id", type=int, help="ID книги на author.today")
    parser.add_argument(
        "--work-id",
        type=int,
        help="(устар.) то же, что --book-id",
    )
    parser.add_argument(
        "--fetched-from",
        type=str,
        required=True,
        help="Начало диапазона fetched_at (ISO), например 2026-06-02T09:12:33.123",
    )
    parser.add_argument(
        "--fetched-to",
        type=str,
        required=True,
        help="Конец диапазона fetched_at (ISO), например 2026-06-02T10:00:00",
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

    try:
        fetched_from = _parse_fetched_at(args.fetched_from)
        fetched_to = _parse_fetched_at(args.fetched_to)
    except ValueError as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 1

    if fetched_from > fetched_to:
        print("Ошибка: --fetched-from должен быть меньше или равен --fetched-to", file=sys.stderr)
        return 1

    repo = create_mssql_repository(settings)
    preview = repo.preview_delete_runs_by_fetched_at(book_id, fetched_from, fetched_to)

    print(
        f"Фильтр: book_id={book_id}, "
        f"fetched_at от {args.fetched_from} до {args.fetched_to}"
    )
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

    result = repo.delete_runs_by_fetched_at(book_id, fetched_from, fetched_to)
    print(f"Удалено chapter_reads: {result.deleted_reads}")
    print(f"Удалено fetch_runs: {result.deleted_runs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
