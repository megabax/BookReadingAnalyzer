from __future__ import annotations

import csv
import json
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


def save_json(table: StatsTable, path: Path) -> None:
    path.write_text(
        json.dumps({"dates": table.dates, "rows": table.rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_snapshot_raw(snapshot: ReadSnapshot, path: Path) -> None:
    """Сохранить снимок в JSON (промежуточный формат до БД)."""
    data = {
        "work_id": snapshot.work_id,
        "period_start": snapshot.period_start.isoformat(),
        "period_end": snapshot.period_end.isoformat(),
        "fetched_at": snapshot.fetched_at.isoformat(),
        "dates": [d.isoformat() for d in snapshot.dates],
        "chapters": list(snapshot.chapters),
        "values": [list(row) for row in snapshot.values],
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
