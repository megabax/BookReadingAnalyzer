from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from author_today.domain.models import ReadSnapshot
from author_today.storage.mssql.connection import connect
from config.settings import Settings

SCHEMA_PATH = Path(__file__).resolve().parent / "mssql" / "schema.sql"

# chapter_order, chapter_name, total_views
ChapterViewsRow = tuple[int, str, int]
# read_date -> chapter_order -> (chapter_name, views)
DailyChapterMatrix = dict[date, dict[int, tuple[str, int]]]

_RUNS_FETCHED_AT_FILTER = "fr.work_id = ? AND fr.fetched_at >= ? AND fr.fetched_at <= ?"


@dataclass(frozen=True)
class DeleteRunsPreview:
    run_ids: tuple[int, ...]
    runs_count: int
    reads_count: int


@dataclass(frozen=True)
class DeleteRunsResult(DeleteRunsPreview):
    deleted_reads: int
    deleted_runs: int


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
            # Book must exist for FK fetch_runs.work_id -> books.id
            cursor.execute(
                """
                IF NOT EXISTS (SELECT 1 FROM dbo.books WHERE id = ?)
                    INSERT INTO dbo.books (id) VALUES (?)
                """,
                snapshot.book_id,
                snapshot.book_id,
            )
            cursor.execute(
                """
                INSERT INTO dbo.fetch_runs (work_id, period_start, period_end, fetched_at)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?)
                """,
                snapshot.book_id,
                snapshot.period_start,
                snapshot.period_end,
                snapshot.fetched_at,
            )
            run_id = int(cursor.fetchone()[0])

            if rows:
                cursor.fast_executemany = True
                cursor.executemany(
                    """
                    INSERT INTO dbo.chapter_reads (run_id, read_date, chapter_order, chapter_name, views)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (run_id, read_date, chapter_order, chapter, views)
                        for read_date, chapter_order, chapter, views in rows
                    ],
                )
            conn.commit()
            return run_id

    def list_runs(self, book_id: int, *, limit: int = 20) -> list[dict]:
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
                book_id,
            )
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def load_snapshot(
        self,
        book_id: int,
        period_start: date,
        period_end: date,
    ) -> ReadSnapshot:
        """Агрегированный снимок прочтений за период (все run'ы книги)."""
        reads_sql = """
            SELECT
                cr.read_date,
                cr.chapter_order,
                cr.chapter_name,
                SUM(COALESCE(cr.views, 0)) AS views
            FROM dbo.chapter_reads cr
            INNER JOIN dbo.fetch_runs fr ON fr.id = cr.run_id
            WHERE fr.work_id = ?
              AND cr.read_date >= ?
              AND cr.read_date <= ?
            GROUP BY cr.read_date, cr.chapter_order, cr.chapter_name
            ORDER BY cr.read_date, cr.chapter_order
        """
        fetched_sql = """
            SELECT MAX(fr.fetched_at)
            FROM dbo.fetch_runs fr
            INNER JOIN dbo.chapter_reads cr ON cr.run_id = fr.id
            WHERE fr.work_id = ?
              AND cr.read_date >= ?
              AND cr.read_date <= ?
        """
        params = (book_id, period_start, period_end)
        with connect(self.settings) as conn:
            cursor = conn.cursor()
            cursor.execute(reads_sql, params)
            rows: list[tuple[date, int, str, int]] = []
            for read_date, chapter_order, chapter_name, views in cursor.fetchall():
                d = read_date if isinstance(read_date, date) else date.fromisoformat(str(read_date)[:10])
                rows.append((d, int(chapter_order), str(chapter_name), int(views)))
            cursor.execute(fetched_sql, params)
            fetched_raw = cursor.fetchone()[0]
            if fetched_raw is None:
                fetched_at = datetime.now()
            elif isinstance(fetched_raw, datetime):
                fetched_at = fetched_raw
            else:
                fetched_at = datetime.fromisoformat(str(fetched_raw).replace("Z", "+00:00"))

        return ReadSnapshot.from_aggregated_rows(
            book_id=book_id,
            period_start=period_start,
            period_end=period_end,
            fetched_at=fetched_at,
            rows=rows,
        )

    def aggregate_chapter_views(
        self,
        book_id: int,
        period_start: date,
        period_end: date,
    ) -> list[ChapterViewsRow]:
        """Сумма просмотров по главам за период (все run'ы книги)."""
        snapshot = self.load_snapshot(book_id, period_start, period_end)
        return snapshot.chapter_totals()

    def daily_chapter_matrix(
        self,
        book_id: int,
        period_start: date,
        period_end: date,
    ) -> DailyChapterMatrix:
        """Дневная матрица просмотров: дата → chapter_order → (имя, views)."""
        return self.load_snapshot(book_id, period_start, period_end).daily_matrix()

    def preview_delete_runs_by_fetched_at(
        self,
        book_id: int,
        fetched_from: datetime,
        fetched_to: datetime,
    ) -> DeleteRunsPreview:
        """Сколько run'ов и строк chapter_reads попадут под фильтр fetched_at."""
        params = (book_id, fetched_from, fetched_to)
        runs_sql = f"SELECT fr.id FROM dbo.fetch_runs fr WHERE {_RUNS_FETCHED_AT_FILTER} ORDER BY fr.id"
        reads_sql = (
            "SELECT COUNT(*) "
            "FROM dbo.chapter_reads cr "
            f"WHERE cr.run_id IN (SELECT fr.id FROM dbo.fetch_runs fr WHERE {_RUNS_FETCHED_AT_FILTER})"
        )
        with connect(self.settings) as conn:
            cursor = conn.cursor()
            cursor.execute(runs_sql, params)
            run_ids = tuple(int(row[0]) for row in cursor.fetchall())
            cursor.execute(reads_sql, params)
            reads_count = int(cursor.fetchone()[0])
        return DeleteRunsPreview(
            run_ids=run_ids,
            runs_count=len(run_ids),
            reads_count=reads_count,
        )

    def delete_runs_by_fetched_at(
        self,
        book_id: int,
        fetched_from: datetime,
        fetched_to: datetime,
    ) -> DeleteRunsResult:
        """Удалить chapter_reads и fetch_runs по book_id и диапазону fetched_at."""
        preview = self.preview_delete_runs_by_fetched_at(book_id, fetched_from, fetched_to)
        if preview.runs_count == 0:
            return DeleteRunsResult(
                run_ids=preview.run_ids,
                runs_count=0,
                reads_count=0,
                deleted_reads=0,
                deleted_runs=0,
            )

        params = (book_id, fetched_from, fetched_to)
        delete_reads_sql = (
            "DELETE cr "
            "FROM dbo.chapter_reads cr "
            f"WHERE cr.run_id IN (SELECT fr.id FROM dbo.fetch_runs fr WHERE {_RUNS_FETCHED_AT_FILTER})"
        )
        delete_runs_sql = f"DELETE fr FROM dbo.fetch_runs fr WHERE {_RUNS_FETCHED_AT_FILTER}"

        with connect(self.settings) as conn:
            cursor = conn.cursor()
            cursor.execute(delete_reads_sql, params)
            deleted_reads = cursor.rowcount if cursor.rowcount >= 0 else preview.reads_count
            cursor.execute(delete_runs_sql, params)
            deleted_runs = cursor.rowcount if cursor.rowcount >= 0 else preview.runs_count
            conn.commit()

        return DeleteRunsResult(
            run_ids=preview.run_ids,
            runs_count=preview.runs_count,
            reads_count=preview.reads_count,
            deleted_reads=deleted_reads,
            deleted_runs=deleted_runs,
        )

    @staticmethod
    def _chapter_rows(snapshot: ReadSnapshot) -> list[tuple]:
        rows: list[tuple] = []
        for day_idx, read_date in enumerate(snapshot.dates):
            for chapter_idx, chapter in enumerate(snapshot.chapters):
                rows.append(
                    (
                        read_date,
                        chapter_idx + 1,  # порядок главы ровно как на сайте
                        chapter,
                        snapshot.values[chapter_idx][day_idx],
                    )
                )
        return rows


def create_mssql_repository(settings: Settings) -> MssqlReadRepository:
    if not settings.has_mssql():
        raise RuntimeError(
            "MS SQL не настроен. Укажите MSSQL_CONNECTION_STRING или MSSQL_SERVER + MSSQL_DATABASE в .env"
        )
    return MssqlReadRepository(settings)
