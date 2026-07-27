"""Контракт хранилища снимков прочтений (DIP: слои выше зависят от Protocol)."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Protocol

from author_today.domain.models import ReadSnapshot

if TYPE_CHECKING:
    from author_today.storage.mssql_repo import (
        BookLoadInfo,
        ChapterViewsRow,
        DailyChapterMatrix,
        DeleteRunsPreview,
        DeleteRunsResult,
        RunDateCoverage,
    )


class ReadRepository(Protocol):
    """
    Абстракция поверх конкретной СУБД.

    Сейчас реализация — MS SQL (`MssqlReadRepository`). Новая БД = новый класс
    с теми же методами + ветка в `get_repository()`.
    """

    def ensure_schema(self) -> None:
        """Создать таблицы, если их ещё нет."""

    def save_snapshot(self, snapshot: ReadSnapshot) -> int:
        """Сохранить снимок; вернуть run_id."""

    def list_runs(self, book_id: int, *, limit: int = 20) -> list[dict]:
        """Последние загрузки книги (от новых к старым)."""

    def get_book_load_info(self, book_id: int, *, limit: int = 50) -> BookLoadInfo:
        """Загрузки + фактический диапазон read_date."""

    def list_run_date_coverage(self, book_id: int | None = None) -> list[RunDateCoverage]:
        """Покрытие дней chapter_reads по run'ам."""

    def list_books(self) -> list[dict]:
        """Книги из каталога БД."""

    def load_snapshot(
        self,
        book_id: int,
        period_start: date,
        period_end: date,
    ) -> ReadSnapshot:
        """Собрать ReadSnapshot из chapter_reads за период."""

    def aggregate_chapter_views(
        self,
        book_id: int,
        period_start: date,
        period_end: date,
    ) -> list[ChapterViewsRow]:
        """Сумма просмотров по главам за период."""

    def daily_chapter_matrix(
        self,
        book_id: int,
        period_start: date,
        period_end: date,
    ) -> DailyChapterMatrix:
        """Матрица день → глава → (имя, views)."""

    def preview_delete_runs_by_fetched_at(
        self,
        book_id: int,
        fetched_from: datetime,
        fetched_to: datetime,
    ) -> DeleteRunsPreview: ...

    def preview_delete_runs_by_period(
        self,
        book_id: int,
        period_start: date,
        period_end: date,
    ) -> DeleteRunsPreview: ...

    def delete_runs_by_fetched_at(
        self,
        book_id: int,
        fetched_from: datetime,
        fetched_to: datetime,
    ) -> DeleteRunsResult: ...

    def delete_runs_by_period(
        self,
        book_id: int,
        period_start: date,
        period_end: date,
    ) -> DeleteRunsResult: ...
