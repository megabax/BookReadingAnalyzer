"""Тесты каталога книг (только MS SQL)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from author_today.services.books import BookOption, load_book_catalog
from config.settings import Settings


def test_load_book_catalog_without_mssql():
    settings = Settings(mssql_server=None, mssql_database=None, mssql_connection_string=None)
    assert load_book_catalog(settings) == []
    assert load_book_catalog(None) == []


def test_load_book_catalog_from_database():
    settings = Settings(
        mssql_server="localhost",
        mssql_database="AuthorToday",
        mssql_user="sa",
        mssql_password="x",
    )
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
