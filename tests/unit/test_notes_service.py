"""Тесты сервиса заметок к книге."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from author_today.errors import AuthorTodayError, DataNotFoundError
from author_today.services import notes as notes_service
from author_today.storage.mssql_repo import BookNote
from config.settings import Settings


def _settings() -> Settings:
    return Settings(
        mssql_server="localhost",
        mssql_database="AuthorToday",
        mssql_user="sa",
        mssql_password="x",
    )


def test_normalize_note_body():
    assert notes_service.normalize_note_body("  реклама  ") == "реклама"
    with pytest.raises(AuthorTodayError, match="пустым"):
        notes_service.normalize_note_body("   ")
    with pytest.raises(AuthorTodayError, match="длинный"):
        notes_service.normalize_note_body("x" * 1001)


@patch("author_today.services.notes.get_repository")
def test_create_book_note(mock_get_repo):
    repo = MagicMock()
    repo.create_book_note.return_value = BookNote(
        note_id=1,
        book_id=10,
        note_date=date(2026, 7, 1),
        body="реклама",
    )
    mock_get_repo.return_value = repo

    note = notes_service.create_book_note(
        _settings(), 10, date(2026, 7, 1), "  реклама  "
    )

    assert note.body == "реклама"
    repo.create_book_note.assert_called_once_with(10, date(2026, 7, 1), "реклама")


@patch("author_today.services.notes.get_repository")
def test_delete_book_note_missing(mock_get_repo):
    repo = MagicMock()
    repo.delete_book_note.return_value = False
    mock_get_repo.return_value = repo

    with pytest.raises(DataNotFoundError):
        notes_service.delete_book_note(_settings(), 10, 99)
