"""Заметки к книге (дата + текст) для UI и отчётов."""

from __future__ import annotations

from datetime import date

from author_today.errors import AuthorTodayError, ConfigError, DataNotFoundError
from author_today.storage.factory import get_repository
from author_today.storage.mssql_repo import BookNote
from config.settings import Settings

MAX_NOTE_BODY_LEN = 1000


def _require_mssql(settings: Settings) -> None:
    if not settings.has_mssql():
        raise ConfigError(
            "MS SQL не настроен. Укажите MSSQL_* или MSSQL_CONNECTION_STRING в .env"
        )


def normalize_note_body(body: str) -> str:
    cleaned = str(body).strip()
    if not cleaned:
        raise AuthorTodayError("Текст заметки не может быть пустым.")
    if len(cleaned) > MAX_NOTE_BODY_LEN:
        raise AuthorTodayError(
            f"Текст слишком длинный ({len(cleaned)} символов). "
            f"Максимум {MAX_NOTE_BODY_LEN}."
        )
    return cleaned


def list_book_notes(
    settings: Settings,
    book_id: int,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[BookNote]:
    _require_mssql(settings)
    return get_repository(settings).list_book_notes(
        book_id, date_from=date_from, date_to=date_to
    )


def create_book_note(
    settings: Settings,
    book_id: int,
    note_date: date,
    body: str,
) -> BookNote:
    _require_mssql(settings)
    return get_repository(settings).create_book_note(
        book_id, note_date, normalize_note_body(body)
    )


def update_book_note(
    settings: Settings,
    book_id: int,
    note_id: int,
    *,
    note_date: date,
    body: str,
) -> BookNote:
    _require_mssql(settings)
    updated = get_repository(settings).update_book_note(
        book_id,
        note_id,
        note_date=note_date,
        body=normalize_note_body(body),
    )
    if updated is None:
        raise DataNotFoundError(
            f"Заметка id={note_id} не найдена для book_id={book_id}"
        )
    return updated


def delete_book_note(settings: Settings, book_id: int, note_id: int) -> None:
    _require_mssql(settings)
    if not get_repository(settings).delete_book_note(book_id, note_id):
        raise DataNotFoundError(
            f"Заметка id={note_id} не найдена для book_id={book_id}"
        )
