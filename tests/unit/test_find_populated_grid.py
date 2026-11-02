"""Ожидание заполненного Kendo Grid (не заглушки)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from author_today.parse.kendo_grid import find_populated_stats_grid


def test_find_populated_stats_grid_none_while_empty_shell():
    driver = MagicMock()
    shell = MagicMock()
    shell.text = "У вас пока нет статистики..."
    shell.find_elements.return_value = []
    driver.find_elements.return_value = [shell]

    with patch(
        "author_today.parse.kendo_grid._kendo_datasource_has_rows",
        return_value=False,
    ):
        assert find_populated_stats_grid(driver) is None


def test_find_populated_stats_grid_returns_scored_grid():
    driver = MagicMock()
    grid = MagicMock()
    grid.text = "Часть\nСтраница книги\nГлава 1\n01.10 02.10\n10 3"
    grid.find_elements.return_value = []
    driver.find_elements.return_value = [grid]

    with patch(
        "author_today.parse.kendo_grid._kendo_datasource_has_rows",
        return_value=False,
    ):
        assert find_populated_stats_grid(driver) is grid


def test_find_populated_stats_grid_prefers_datasource_ready():
    driver = MagicMock()
    grid = MagicMock()
    grid.text = ""
    driver.find_elements.return_value = [grid]

    with patch(
        "author_today.parse.kendo_grid._kendo_datasource_has_rows",
        return_value=True,
    ):
        assert find_populated_stats_grid(driver) is grid
