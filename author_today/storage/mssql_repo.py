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
_RUNS_PERIOD_FILTER = "fr.work_id = ? AND fr.period_start = ? AND fr.period_end = ?"


@dataclass(frozen=True)
class DeleteRunsPreview:
    run_ids: tuple[int, ...]
    runs_count: int
    reads_count: int


@dataclass(frozen=True)
class DeleteRunsResult(DeleteRunsPreview):
    deleted_reads: int
    deleted_runs: int


@dataclass(frozen=True)
class LoadedRun:
    run_id: int
    period_start: date
    period_end: date
    fetched_at: datetime


@dataclass(frozen=True)
class BookLoadInfo:
    book_id: int
    runs: tuple[LoadedRun, ...]
    read_date_min: date | None
    read_date_max: date | None


@dataclass(frozen=True)
class RunDateCoverage:
    run_id: int
    book_id: int
    book_title: str | None
    period_start: date
    period_end: date
    fetched_at: datetime
    read_dates: frozenset[date]


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

    def get_book_load_info(self, book_id: int, *, limit: int = 50) -> BookLoadInfo:
        """Загрузки книги (fetch_runs) и фактический диапазон read_date в chapter_reads."""
        runs_raw = self.list_runs(book_id, limit=limit)
        runs: list[LoadedRun] = []
        for row in runs_raw:
            fetched_raw = row["fetched_at"]
            if isinstance(fetched_raw, datetime):
                fetched_at = fetched_raw
            else:
                fetched_at = datetime.fromisoformat(str(fetched_raw).replace("Z", "+00:00"))
            period_start = row["period_start"]
            period_end = row["period_end"]
            if not isinstance(period_start, date):
                period_start = date.fromisoformat(str(period_start)[:10])
            if not isinstance(period_end, date):
                period_end = date.fromisoformat(str(period_end)[:10])
            runs.append(
                LoadedRun(
                    run_id=int(row["id"]),
                    period_start=period_start,
                    period_end=period_end,
                    fetched_at=fetched_at,
                )
            )

        with connect(self.settings) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT MIN(cr.read_date), MAX(cr.read_date)
                FROM dbo.chapter_reads cr
                INNER JOIN dbo.fetch_runs fr ON fr.id = cr.run_id
                WHERE fr.work_id = ?
                """,
                book_id,
            )
            row = cursor.fetchone()
            read_min = row[0]
            read_max = row[1]

        def _as_date(value) -> date | None:
            if value is None:
                return None
            if isinstance(value, date):
                return value
            return date.fromisoformat(str(value)[:10])

        return BookLoadInfo(
            book_id=book_id,
            runs=tuple(runs),
            read_date_min=_as_date(read_min),
            read_date_max=_as_date(read_max),
        )

    def list_run_date_coverage(self, book_id: int | None = None) -> list[RunDateCoverage]:
        """Все fetch_runs и множество read_date по каждому run_id."""
        sql = """
            SELECT
                fr.id,
                fr.work_id,
                b.title,
                fr.period_start,
                fr.period_end,
                fr.fetched_at,
                cr.read_date
            FROM dbo.fetch_runs fr
            LEFT JOIN dbo.books b ON b.id = fr.work_id
            LEFT JOIN dbo.chapter_reads cr ON cr.run_id = fr.id
            WHERE (? IS NULL OR fr.work_id = ?)
            ORDER BY fr.work_id, fr.fetched_at DESC, fr.id, cr.read_date
        """
        params = (book_id, book_id)
        grouped: dict[int, dict] = {}

        def _as_date(value) -> date:
            if isinstance(value, date):
                return value
            return date.fromisoformat(str(value)[:10])

        def _as_datetime(value) -> datetime:
            if isinstance(value, datetime):
                return value
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))

        with connect(self.settings) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            for run_id, work_id, title, period_start, period_end, fetched_at, read_date in cursor.fetchall():
                run_id = int(run_id)
                entry = grouped.get(run_id)
                if entry is None:
                    entry = {
                        "book_id": int(work_id),
                        "book_title": str(title) if title is not None else None,
                        "period_start": _as_date(period_start),
                        "period_end": _as_date(period_end),
                        "fetched_at": _as_datetime(fetched_at),
                        "read_dates": set(),
                    }
                    grouped[run_id] = entry
                if read_date is not None:
                    entry["read_dates"].add(_as_date(read_date))

        return [
            RunDateCoverage(
                run_id=run_id,
                book_id=entry["book_id"],
                book_title=entry["book_title"],
                period_start=entry["period_start"],
                period_end=entry["period_end"],
                fetched_at=entry["fetched_at"],
                read_dates=frozenset(entry["read_dates"]),
            )
            for run_id, entry in grouped.items()
        ]

    def list_books(self) -> list[dict]:
        """Книги, уже известные БД (dbo.books)."""
        with connect(self.settings) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, title
                FROM dbo.books
                ORDER BY id
                """
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

    def _preview_delete_runs(self, runs_filter: str, params: tuple) -> DeleteRunsPreview:
        runs_sql = f"SELECT fr.id FROM dbo.fetch_runs fr WHERE {runs_filter} ORDER BY fr.id"
        reads_sql = (
            "SELECT COUNT(*) "
            "FROM dbo.chapter_reads cr "
            f"WHERE cr.run_id IN (SELECT fr.id FROM dbo.fetch_runs fr WHERE {runs_filter})"
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

    def _delete_runs(self, runs_filter: str, params: tuple, preview: DeleteRunsPreview) -> DeleteRunsResult:
        if preview.runs_count == 0:
            return DeleteRunsResult(
                run_ids=preview.run_ids,
                runs_count=0,
                reads_count=0,
                deleted_reads=0,
                deleted_runs=0,
            )

        delete_reads_sql = (
            "DELETE cr "
            "FROM dbo.chapter_reads cr "
            f"WHERE cr.run_id IN (SELECT fr.id FROM dbo.fetch_runs fr WHERE {runs_filter})"
        )
        delete_runs_sql = f"DELETE fr FROM dbo.fetch_runs fr WHERE {runs_filter}"

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

    def preview_delete_runs_by_fetched_at(
        self,
        book_id: int,
        fetched_from: datetime,
        fetched_to: datetime,
    ) -> DeleteRunsPreview:
        """Сколько run'ов и строк chapter_reads попадут под фильтр fetched_at."""
        params = (book_id, fetched_from, fetched_to)
        return self._preview_delete_runs(_RUNS_FETCHED_AT_FILTER, params)

    def preview_delete_runs_by_period(
        self,
        book_id: int,
        period_start: date,
        period_end: date,
    ) -> DeleteRunsPreview:
        """Сколько run'ов и строк chapter_reads попадут под фильтр period_start/period_end."""
        params = (book_id, period_start, period_end)
        return self._preview_delete_runs(_RUNS_PERIOD_FILTER, params)

    def delete_runs_by_fetched_at(
        self,
        book_id: int,
        fetched_from: datetime,
        fetched_to: datetime,
    ) -> DeleteRunsResult:
        """Удалить chapter_reads и fetch_runs по book_id и диапазону fetched_at."""
        params = (book_id, fetched_from, fetched_to)
        preview = self.preview_delete_runs_by_fetched_at(book_id, fetched_from, fetched_to)
        return self._delete_runs(_RUNS_FETCHED_AT_FILTER, params, preview)

    def delete_runs_by_period(
        self,
        book_id: int,
        period_start: date,
        period_end: date,
    ) -> DeleteRunsResult:
        """Удалить chapter_reads и fetch_runs по book_id и заявленному периоду загрузки."""
        params = (book_id, period_start, period_end)
        preview = self.preview_delete_runs_by_period(book_id, period_start, period_end)
        return self._delete_runs(_RUNS_PERIOD_FILTER, params, preview)

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
