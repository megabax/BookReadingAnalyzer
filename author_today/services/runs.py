"""Операции с fetch_runs для UI/CLI."""

from __future__ import annotations

from author_today.errors import ConfigError, DataNotFoundError
from author_today.storage.factory import get_repository
from author_today.storage.mssql_repo import DeleteRunsPreview, DeleteRunsResult
from config.settings import Settings


def _require_mssql(settings: Settings) -> None:
    if not settings.has_mssql():
        raise ConfigError(
            "MS SQL не настроен. Укажите MSSQL_* или MSSQL_CONNECTION_STRING в .env"
        )


def preview_delete_run(
    settings: Settings,
    book_id: int,
    run_id: int,
) -> DeleteRunsPreview:
    """Сколько chapter_reads удалится вместе с fetch_run (с проверкой book_id)."""
    _require_mssql(settings)
    preview = get_repository(settings).preview_delete_run(book_id, run_id)
    if preview.runs_count == 0:
        raise DataNotFoundError(
            f"run_id={run_id} не найден для book_id={book_id} "
            "(или принадлежит другой книге)."
        )
    return preview


def delete_run(
    settings: Settings,
    book_id: int,
    run_id: int,
) -> DeleteRunsResult:
    """Удалить fetch_run и связанные chapter_reads."""
    _require_mssql(settings)
    preview = preview_delete_run(settings, book_id, run_id)
    result = get_repository(settings).delete_run(book_id, run_id)
    if result.deleted_runs == 0:
        raise DataNotFoundError(
            f"Не удалось удалить run_id={run_id} для book_id={book_id}"
        )
    return result
