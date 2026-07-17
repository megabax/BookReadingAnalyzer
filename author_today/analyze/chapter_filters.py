"""Фильтры глав для воронки и compare."""

from __future__ import annotations

from collections.abc import Iterable

BOOK_PAGE_NAME = "страница книги"

ChapterRow = tuple[int, str, int]  # chapter_order, chapter_name, views


def is_book_page(name: str) -> bool:
    return name.strip().lower() == BOOK_PAGE_NAME


def filter_chapter_rows(
    rows: Iterable[ChapterRow],
    *,
    skip_book_page: bool = False,
) -> list[ChapterRow]:
    """Отсортировать по chapter_order и опционально убрать «Страница книги»."""
    filtered: list[ChapterRow] = []
    for order, name, views in sorted(rows, key=lambda r: r[0]):
        if skip_book_page and is_book_page(name):
            continue
        filtered.append((order, name, views))
    return filtered
