from __future__ import annotations

from pathlib import Path

from author_today.domain.models import ReadSnapshot
from author_today.storage.mssql.connection import connect
from config.settings import Settings

SCHEMA_PATH = Path(__file__).resolve().parent / "mssql" / "schema.sql"


class MssqlReadRepository:
    """Сохранение снимков прочтений в MS SQL Server."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def ensure_schema(self) -> None:
        """Создать таблицы, если их ещё нет."""
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        batches = [b.strip() for b in sql.split("GO") if b.strip()]
        with connect(self.settings) as conn:
            cursor = conn.cursor()
            for batch in batches:
                cursor.execute(batch)
            conn.commit()

    def save_snapshot(self, snapshot: ReadSnapshot) -> int:
        """Сохранить снимок: fetch_runs + chapter_reads (структура dates)."""
        rows = self._chapter_rows(snapshot)
        with connect(self.settings) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO dbo.fetch_runs (work_id, period_start, period_end, fetched_at)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?)
                """,
                snapshot.work_id,
                snapshot.period_start,
                snapshot.period_end,
                snapshot.fetched_at,
            )
            run_id = int(cursor.fetchone()[0])

            if rows:
                cursor.fast_executemany = True
                cursor.executemany(
                    """
                    INSERT INTO dbo.chapter_reads (run_id, read_date, chapter_name, views)
                    VALUES (?, ?, ?, ?)
                    """,
                    [(run_id, read_date, chapter, views) for read_date, chapter, views in rows],
                )
            conn.commit()
            return run_id

    def list_runs(self, work_id: int, *, limit: int = 20) -> list[dict]:
        with connect(self.settings) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT TOP (?) id, work_id, period_start, period_end, fetched_at
                FROM dbo.fetch_runs
                WHERE work_id = ?
                ORDER BY fetched_at DESC
                """,
                limit,
                work_id,
            )
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    @staticmethod
    def _chapter_rows(snapshot: ReadSnapshot) -> list[tuple]:
        rows: list[tuple] = []
        for day_idx, read_date in enumerate(snapshot.dates):
            for chapter_idx, chapter in enumerate(snapshot.chapters):
                rows.append((read_date, chapter, snapshot.values[chapter_idx][day_idx]))
        return rows


def create_mssql_repository(settings: Settings) -> MssqlReadRepository:
    if not settings.has_mssql():
        raise RuntimeError(
            "MS SQL не настроен. Укажите MSSQL_CONNECTION_STRING или MSSQL_SERVER + MSSQL_DATABASE в .env"
        )
    return MssqlReadRepository(settings)
