"""Распознавание подписей глав в Kendo-парсере."""

from __future__ import annotations

from author_today.parse.kendo_grid import _is_chapter_label, _table_row_allowed


def test_epilog_is_chapter():
    assert _is_chapter_label("Эпилог")
    assert _is_chapter_label("эпилог")
    assert _table_row_allowed("Эпилог")


def test_instead_of_epilog_still_chapter():
    assert _is_chapter_label("Вместо эпилога")
    assert _table_row_allowed("Вместо эпилога")


def test_regular_chapters():
    assert _is_chapter_label("Глава 1")
    assert _is_chapter_label("Интерлюдия")
    assert _table_row_allowed("Страница книги")
    assert not _is_chapter_label("Часть")
    assert not _table_row_allowed("Часть")
    assert not _table_row_allowed("")
