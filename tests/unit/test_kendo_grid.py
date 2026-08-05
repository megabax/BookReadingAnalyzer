"""Тесты сборки Kendo Grid при горизонтальной прокрутке."""

from __future__ import annotations

from author_today.parse.kendo_grid import (
    _parse_number,
    _values_for_date_indices,
    iter_scroll_row_indices,
    merge_scroll_slice,
    stats_table_from_maps,
)


def test_parse_number_int_and_float():
    assert _parse_number("12") == 12.0
    assert _parse_number("12,5") == 12.5
    assert _parse_number("1 234.5") == 1234.5
    assert _parse_number("") is None
    assert _parse_number("abc") is None


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


def test_vertical_passes_collect_chapters_in_order():
    date_order: list[str] = []
    chapter_values: dict[str, dict[str, int | None]] = {}
    chapter_order: list[str] = []

    merge_scroll_slice(
        date_order,
        chapter_values,
        chapter="Глава 1",
        dates_batch=["01.06"],
        values=[1],
        chapter_order=chapter_order,
    )
    merge_scroll_slice(
        date_order,
        chapter_values,
        chapter="Глава 16",
        dates_batch=["01.06"],
        values=[2],
        chapter_order=chapter_order,
    )

    table = stats_table_from_maps(date_order, chapter_values, chapter_order)
    assert [row["chapter"] for row in table.rows] == ["Глава 1", "Глава 16"]
    assert table.rows[1]["01.06"] == 2


def test_extract_kendo_split_prefers_datasource_skips_dom_scroll():
    """Если dataSource уже дал строки — DOM-прокрутку не запускаем."""
    from unittest.mock import MagicMock, patch

    from author_today.domain.models import StatsTable
    from author_today.parse.kendo_grid import _extract_kendo_split

    ds = StatsTable(
        dates=["01.06", "02.06"],
        rows=[{"chapter": "Глава 1", "01.06": 1, "02.06": 2}],
    )
    grid = MagicMock()
    driver = MagicMock()

    with (
        patch(
            "author_today.parse.kendo_grid._extract_kendo_datasource",
            return_value=ds,
        ) as mock_ds,
        patch(
            "author_today.parse.kendo_grid._extract_via_dom_scroll",
        ) as mock_dom,
    ):
        result = _extract_kendo_split(grid, driver)

    assert result is ds
    mock_ds.assert_called_once_with(driver, grid)
    mock_dom.assert_not_called()
    grid.find_elements.assert_not_called()


def test_extract_kendo_split_falls_back_to_dom_when_datasource_empty():
    from unittest.mock import MagicMock, patch

    from author_today.domain.models import StatsTable
    from author_today.parse.kendo_grid import _extract_kendo_split

    dom = StatsTable(
        dates=["01.06"],
        rows=[{"chapter": "Глава 1", "01.06": 10}],
    )
    grid = MagicMock()
    locked = MagicMock()
    scroll = MagicMock()
    grid.find_elements.side_effect = [
        [locked],  # .k-grid-content-locked
        [scroll],  # .k-grid-content.k-auto-scrollable
    ]
    driver = MagicMock()

    with (
        patch(
            "author_today.parse.kendo_grid._extract_kendo_datasource",
            return_value=None,
        ),
        patch(
            "author_today.parse.kendo_grid._header_scroll_el",
            return_value=None,
        ),
        patch(
            "author_today.parse.kendo_grid._extract_via_dom_scroll",
            return_value=dom,
        ) as mock_dom,
    ):
        result = _extract_kendo_split(grid, driver)

    assert result is dom
    mock_dom.assert_called_once()
