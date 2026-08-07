"""Тесты каталога книг (только MS SQL)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from author_today.errors import AuthorTodayError, DataNotFoundError
from author_today.services.books import (
    BookOption,
    load_book_catalog,
    normalize_book_title,
    update_book_title,
)
from config.settings import Settings


def _mssql_settings() -> Settings:
    return Settings(
        mssql_server="localhost",
        mssql_database="AuthorToday",
        mssql_user="sa",
        mssql_password="x",
    )


def test_load_book_catalog_without_mssql():
    settings = Settings(mssql_server=None, mssql_database=None, mssql_connection_string=None)
    assert load_book_catalog(settings) == []
    assert load_book_catalog(None) == []


def test_load_book_catalog_from_database():
    settings = _mssql_settings()
    repo = MagicMock()
    repo.list_books.return_value = [
        {"id": 323389, "title": "Пример"},
        {"id": 172953, "title": "  Рыба  "},
        {"id": 1, "title": None},
    ]
    with patch("author_today.services.books.get_repository", return_value=repo):
        catalog = load_book_catalog(settings)

    assert [book.book_id for book in catalog] == [1, 172953, 323389]
    assert catalog[0] == BookOption(book_id=1, title=None)
    assert catalog[1].title == "Рыба"
    assert catalog[1].label == "172953 — Рыба"
    assert catalog[2].label == "323389 — Пример"


def test_normalize_book_title():
    assert normalize_book_title(None) is None
    assert normalize_book_title("") is None
    assert normalize_book_title("  ") is None
    assert normalize_book_title("  Рыба  ") == "Рыба"
    with pytest.raises(AuthorTodayError, match="слишком длинное"):
        normalize_book_title("x" * 301)


@patch("author_today.services.books.get_repository")
def test_update_book_title_ok(mock_get_repo):
    repo = MagicMock()
    repo.update_book_title.return_value = True
    mock_get_repo.return_value = repo

    saved = update_book_title(_mssql_settings(), 172953, "  Новое имя  ")

    assert saved == "Новое имя"
    repo.update_book_title.assert_called_once_with(172953, "Новое имя")


@patch("author_today.services.books.get_repository")
def test_update_book_title_clear(mock_get_repo):
    repo = MagicMock()
    repo.update_book_title.return_value = True
    mock_get_repo.return_value = repo

    assert update_book_title(_mssql_settings(), 1, "   ") is None
    repo.update_book_title.assert_called_once_with(1, None)


@patch("author_today.services.books.get_repository")
def test_update_book_title_not_found(mock_get_repo):
    repo = MagicMock()
    repo.update_book_title.return_value = False
    mock_get_repo.return_value = repo

    with pytest.raises(DataNotFoundError, match="не найдена"):
        update_book_title(_mssql_settings(), 999, "X")
