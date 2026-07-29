"""Каталог книг для UI из dbo.books."""

from __future__ import annotations

from dataclasses import dataclass

from author_today.storage.factory import get_repository
from author_today.storage.mssql_repo import BookLoadInfo
from config.settings import Settings


@dataclass(frozen=True)
class BookOption:
    book_id: int
    title: str | None

    @property
    def label(self) -> str:
        if self.title:
            return f"{self.book_id} — {self.title}"
        return f"{self.book_id}"


def load_book_catalog(settings: Settings | None = None) -> list[BookOption]:
    """Список книг из MS SQL (`dbo.books`). Без БД — пустой каталог."""
    if settings is None or not settings.has_mssql():
        return []

    repo = get_repository(settings)
    books: list[BookOption] = []
    for row in repo.list_books():
        book_id = int(row["id"])
        db_title = row.get("title")
        title = str(db_title).strip() if db_title is not None and str(db_title).strip() else None
        books.append(BookOption(book_id=book_id, title=title))
    return sorted(books, key=lambda item: item.book_id)


def load_book_data_info(settings: Settings, book_id: int, *, limit: int = 50) -> BookLoadInfo | None:
    """Периоды загрузок и покрытие read_date в БД для книги."""
    if not settings.has_mssql():
        return None
    return get_repository(settings).get_book_load_info(book_id, limit=limit)
