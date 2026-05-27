from __future__ import annotations

from author_today.domain.models import ReadSnapshot, StatsTable


def summary_from_table(table: StatsTable) -> dict:
    """Краткая сводка по таблице (заготовка для отчётов)."""
    totals: dict[str, int] = {}
    for row in table.rows:
        chapter = str(row["chapter"])
        total = sum(v for v in row.values() if isinstance(v, int))
        totals[chapter] = total
    top = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:10]
    return {"chapters_count": len(table.rows), "days_count": len(table.dates), "top_chapters": top}


def summary_from_snapshot(snapshot: ReadSnapshot) -> dict:
    """Сводка по нормализованному снимку."""
    totals = []
    for chapter, row in zip(snapshot.chapters, snapshot.values):
        totals.append((chapter, sum(v or 0 for v in row)))
    top = sorted(totals, key=lambda x: x[1], reverse=True)[:10]
    return {
        "book_id": snapshot.book_id,
        "period": f"{snapshot.period_start} — {snapshot.period_end}",
        "top_chapters": top,
    }
