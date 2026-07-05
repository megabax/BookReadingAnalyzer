"""Каталог книг для UI: config/books.yaml + dbo.books."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from author_today.storage.mssql_repo import BookLoadInfo, create_mssql_repository
from config.settings import ROOT_DIR, Settings

BOOKS_YAML_PATH = ROOT_DIR / "config" / "books.yaml"


@dataclass(frozen=True)
class BookOption:
    book_id: int
    title: str | None
    in_yaml: bool
    in_database: bool

    @property
    def label(self) -> str:
        name = f"{self.book_id}"
        if self.title:
            name = f"{self.book_id} — {self.title}"
        tags: list[str] = []
        if self.in_database:
            tags.append("БД")
        if self.in_yaml:
            tags.append("каталог")
        if tags:
            name = f"{name} ({', '.join(tags)})"
        return name


def _parse_books_yaml(path: Path = BOOKS_YAML_PATH) -> list[tuple[int, str | None]]:
    if not path.is_file():
        return []

    books: list[tuple[int, str | None]] = []
    current_id: int | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        id_match = re.match(r"-?\s*book_id:\s*(\d+)", line)
        if id_match:
            current_id = int(id_match.group(1))
            continue
        title_match = re.match(r'title:\s*"(.*)"', line)
        if title_match and current_id is not None:
            books.append((current_id, title_match.group(1)))
            current_id = None
    return books


def _merge_title(yaml_title: str | None, db_title: object) -> str | None:
    """Название из БД важнее YAML (источник правды после первой загрузки)."""
    if db_title is not None and str(db_title).strip():
        return str(db_title).strip()
    return yaml_title


def load_book_catalog(settings: Settings | None = None) -> list[BookOption]:
    """Объединённый список: YAML-каталог и книги из MS SQL."""
    by_id: dict[int, BookOption] = {}

    for book_id, title in _parse_books_yaml():
        by_id[book_id] = BookOption(
            book_id=book_id,
            title=title,
            in_yaml=True,
            in_database=False,
        )

    if settings is not None and settings.has_mssql():
        repo = create_mssql_repository(settings)
        for row in repo.list_books():
            book_id = int(row["id"])
            db_title = row.get("title")
            if book_id in by_id:
                existing = by_id[book_id]
                by_id[book_id] = BookOption(
                    book_id=book_id,
                    title=_merge_title(existing.title, db_title),
                    in_yaml=existing.in_yaml,
                    in_database=True,
                )
            else:
                by_id[book_id] = BookOption(
                    book_id=book_id,
                    title=str(db_title) if db_title else None,
                    in_yaml=False,
                    in_database=True,
                )

    return sorted(by_id.values(), key=lambda item: item.book_id)


def load_book_data_info(settings: Settings, book_id: int, *, limit: int = 50) -> BookLoadInfo | None:
    """Периоды загрузок и покрытие read_date в БД для книги."""
    if not settings.has_mssql():
        return None
    return create_mssql_repository(settings).get_book_load_info(book_id, limit=limit)
