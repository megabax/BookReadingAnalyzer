#!/usr/bin/env python
"""Удаление загрузок из MS SQL по work_id и диапазону fetched_at."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from author_today.storage.mssql.connection import connect
from config.settings import Settings


def _parse_fetched_at(raw_value: str) -> datetime:
    normalized = raw_value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(
            "Неверный формат даты. Используйте YYYY-MM-DDTHH:MM:SS (или с миллисекундами)."
        ) from exc


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Удалить записи из chapter_reads и fetch_runs по work_id и диапазону fetched_at."
    )
    parser.add_argument("--work-id", type=int, required=True, help="work_id книги")
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

    where = "fr.work_id = ? AND fr.fetched_at >= ? AND fr.fetched_at <= ?"
    params = [args.work_id, fetched_from, fetched_to]
    runs_sql = f"SELECT COUNT(*) FROM dbo.fetch_runs fr WHERE {where}"
    run_ids_sql = f"SELECT fr.id FROM dbo.fetch_runs fr WHERE {where} ORDER BY fr.id"
    reads_sql = (
        "SELECT COUNT(*) "
        "FROM dbo.chapter_reads cr "
        f"WHERE cr.run_id IN (SELECT fr.id FROM dbo.fetch_runs fr WHERE {where})"
    )
    delete_reads_sql = (
        "DELETE cr "
        "FROM dbo.chapter_reads cr "
        f"WHERE cr.run_id IN (SELECT fr.id FROM dbo.fetch_runs fr WHERE {where})"
    )
    delete_runs_sql = f"DELETE fr FROM dbo.fetch_runs fr WHERE {where}"

    with connect(settings) as conn:
        cursor = conn.cursor()
        cursor.execute(runs_sql, params)
        runs_count = int(cursor.fetchone()[0])
        cursor.execute(run_ids_sql, params)
        run_ids = [int(row[0]) for row in cursor.fetchall()]
        cursor.execute(reads_sql, params)
        reads_count = int(cursor.fetchone()[0])

        print(
            f"Фильтр: work_id={args.work_id}, "
            f"fetched_at от {args.fetched_from} до {args.fetched_to}"
        )
        if run_ids:
            print("Найденные run_id: " + ", ".join(str(v) for v in run_ids))
        print(f"Найдено fetch_runs: {runs_count}")
        print(f"Найдено chapter_reads: {reads_count}")
        if args.dry_run:
            conn.rollback()
            return 0

        if runs_count == 0:
            conn.rollback()
            print("Нечего удалять.")
            return 0

        if not args.yes:
            answer = input("Удалить найденные записи? [y/N]: ").strip().lower()
            if answer not in ("y", "yes", "д", "да"):
                conn.rollback()
                print("Отменено.")
                return 0

        cursor.execute(delete_reads_sql, params)
        deleted_reads = cursor.rowcount if cursor.rowcount >= 0 else reads_count
        cursor.execute(delete_runs_sql, params)
        deleted_runs = cursor.rowcount if cursor.rowcount >= 0 else runs_count
        conn.commit()

    print(f"Удалено chapter_reads: {deleted_reads}")
    print(f"Удалено fetch_runs: {deleted_runs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

