from __future__ import annotations

from datetime import date, datetime

import json

from author_today.domain.models import ReadSnapshot, StatsTable
from author_today.domain.sales import SaleSnapshot
from author_today.storage.export import save_snapshot_raw
from author_today.storage.factory import get_repository
from config.settings import RAW_DIR, Settings


def persist_snapshot(
    snapshot: ReadSnapshot,
    settings: Settings,
    *,
    save_raw: bool = True,
    save_mssql: bool = True,
) -> None:
    """Сохранить снимок в data/raw и MS SQL (если настроено)."""
    if save_raw:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_path = RAW_DIR / f"reads_{snapshot.book_id}_{stamp}.json"
        save_snapshot_raw(snapshot, raw_path)
        print(f"JSON: {raw_path}")

    if save_mssql and settings.has_mssql():
        repo = get_repository(settings)
        repo.ensure_schema()
        run_id = repo.save_snapshot(snapshot)
        rows_count = sum(len(day["chapters"]) for day in snapshot.to_document()["dates"])
        print(f"MS SQL: run_id={run_id}, записей chapter_reads={rows_count}")


def persist_sale_snapshot(
    snapshot: SaleSnapshot,
    settings: Settings,
    *,
    save_raw: bool = False,
    save_mssql: bool = True,
) -> int | None:
    """Сохранить продажи в MS SQL (+ опционально JSON в data/raw)."""
    run_id: int | None = None
    if save_raw:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_path = RAW_DIR / f"sales_{snapshot.book_id}_{stamp}.json"
        payload = {
            "book_id": snapshot.book_id,
            "period_start": snapshot.period_start.isoformat(),
            "period_end": snapshot.period_end.isoformat(),
            "fetched_at": snapshot.fetched_at.isoformat(),
            "events": [
                {
                    "processed_at": e.processed_at.isoformat(),
                    "book_id": e.book_id,
                    "work_format": e.work_format,
                    "price": e.price,
                    "commission": e.commission,
                    "author_income": e.author_income,
                }
                for e in snapshot.events
            ],
        }
        raw_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"JSON: {raw_path}")

    if save_mssql and settings.has_mssql():
        repo = get_repository(settings)
        repo.ensure_schema()
        run_id = repo.save_sale_snapshot(snapshot)
        print(
            f"MS SQL: sale_run_id={run_id}, записей sale_events={len(snapshot.events)}"
        )
    return run_id


def snapshot_from_table(
    table: StatsTable,
    settings: Settings,
    period_start: date,
    period_end: date,
) -> ReadSnapshot:
    return ReadSnapshot.from_stats_table(
        table,
        book_id=settings.book_id,
        period_start=period_start,
        period_end=period_end,
        value_type=settings.value_type,
    )
