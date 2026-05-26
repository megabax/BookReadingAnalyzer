from __future__ import annotations

from datetime import date, datetime

from author_today.domain.models import ReadSnapshot, StatsTable
from author_today.storage.export import save_snapshot_raw
from author_today.storage.mssql_repo import create_mssql_repository
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
        raw_path = RAW_DIR / f"reads_{snapshot.work_id}_{stamp}.json"
        save_snapshot_raw(snapshot, raw_path)
        print(f"JSON: {raw_path}")

    if save_mssql and settings.has_mssql():
        repo = create_mssql_repository(settings)
        run_id = repo.save_snapshot(snapshot)
        rows_count = sum(len(day["chapters"]) for day in snapshot.to_document()["dates"])
        print(f"MS SQL: run_id={run_id}, записей chapter_reads={rows_count}")


def snapshot_from_table(
    table: StatsTable,
    settings: Settings,
    period_start: date,
    period_end: date,
) -> ReadSnapshot:
    return ReadSnapshot.from_stats_table(
        table,
        work_id=settings.work_id,
        period_start=period_start,
        period_end=period_end,
    )
