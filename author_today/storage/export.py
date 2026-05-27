from __future__ import annotations

import csv
import json
from datetime import date, datetime
from pathlib import Path

from author_today.domain.models import ReadSnapshot, StatsTable


def print_table(table: StatsTable) -> None:
    if not table.rows:
        print("Нет данных.")
        return
    dates = table.dates
    print("\t".join(["chapter", *dates]))
    for row in table.rows:
        line = [str(row["chapter"])]
        for d in dates:
            v = row.get(d)
            line.append("" if v is None else str(v))
        print("\t".join(line))
    print(f"\nСтрок: {len(table.rows)}, дат в заголовке: {len(dates)}")


def save_csv(table: StatsTable, path: Path) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["chapter", *table.dates])
        writer.writeheader()
        for row in table.rows:
            writer.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in writer.fieldnames})


def save_json(
    table: StatsTable,
    path: Path,
    *,
    book_id: int,
    period_start: date,
    period_end: date,
    fetched_at: datetime | None = None,
) -> None:
    """Сохранить JSON: dates[] → { date, chapters[] → { chapter, views } }."""
    snapshot = ReadSnapshot.from_stats_table(
        table,
        book_id=book_id,
        period_start=period_start,
        period_end=period_end,
        fetched_at=fetched_at,
    )
    save_snapshot_raw(snapshot, path)


def save_snapshot_raw(snapshot: ReadSnapshot, path: Path) -> None:
    """Сохранить снимок в JSON (data/raw)."""
    path.write_text(
        json.dumps(snapshot.to_document(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
