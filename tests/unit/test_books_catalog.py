"""Тесты каталога книг."""

from __future__ import annotations

from author_today.services.books import BookOption, _merge_title, _parse_books_yaml, load_book_catalog
from config.settings import Settings


def test_parse_books_yaml(tmp_path):
    yaml_path = tmp_path / "books.yaml"
    yaml_path.write_text(
        'books:\n  - book_id: 172953\n    title: "Тест"\n  - book_id: 1\n    title: "A"\n',
        encoding="utf-8",
    )
    assert _parse_books_yaml(yaml_path) == [(172953, "Тест"), (1, "A")]


def test_load_book_catalog_yaml_only():
    settings = Settings(mssql_server=None, mssql_database=None)
    catalog = load_book_catalog(settings)
    assert any(book.book_id == 172953 for book in catalog)
    book = next(item for item in catalog if item.book_id == 172953)
    assert book.in_yaml
    assert isinstance(book, BookOption)


def test_merge_title_prefers_database():
    assert _merge_title("Заглушка", "Рыба без головы. Апокалипсис") == "Рыба без головы. Апокалипсис"
    assert _merge_title("Из YAML", None) == "Из YAML"
