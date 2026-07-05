"""Тесты сборки Kendo Grid при горизонтальной прокрутке."""

from __future__ import annotations

from author_today.parse.kendo_grid import (
    _values_for_date_indices,
    iter_scroll_row_indices,
    merge_scroll_slice,
    stats_table_from_maps,
)


def test_merge_scroll_slice_two_passes():
    date_order: list[str] = []
    chapter_values: dict[str, dict[str, int | None]] = {}

    merge_scroll_slice(
        date_order,
        chapter_values,
        chapter="Глава 1",
        dates_batch=["01.06", "02.06"],
        values=[1, 2],
    )
    merge_scroll_slice(
        date_order,
        chapter_values,
        chapter="Глава 1",
        dates_batch=["03.06", "04.06"],
        values=[3, 4],
    )

    table = stats_table_from_maps(date_order, chapter_values)
    assert table.dates == ["01.06", "02.06", "03.06", "04.06"]
    assert table.rows[0]["chapter"] == "Глава 1"
    assert table.rows[0]["04.06"] == 4


def test_iter_scroll_row_indices_skips_chast_row():
    labels = ["Часть", "Страница книги", "Глава 1. Тест", "Глава 2. Тест"]
    pairs = iter_scroll_row_indices(labels)
    assert pairs == [
        ("Страница книги", 0),
        ("Глава 1. Тест", 1),
        ("Глава 2. Тест", 2),
    ]


def test_values_for_date_indices_visible_slice():
    values = _values_for_date_indices(["10", "20", "30", "40"], [1, 3])
    assert values == [20, 40]


def test_merge_scroll_slice_overwrites_with_later_pass():
    date_order: list[str] = []
    chapter_values: dict[str, dict[str, int | None]] = {}

    merge_scroll_slice(
        date_order,
        chapter_values,
        chapter="Глава 1",
        dates_batch=["01.06"],
        values=[99],
    )
    merge_scroll_slice(
        date_order,
        chapter_values,
        chapter="Глава 1",
        dates_batch=["01.06"],
        values=[23],
    )

    assert chapter_values["Глава 1"]["01.06"] == 23
