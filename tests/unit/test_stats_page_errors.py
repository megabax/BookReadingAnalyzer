"""Детекция 403/404 на странице отчёта (без Selenium)."""

from __future__ import annotations

import pytest

from author_today.errors import StatsPageError
from author_today.fetch.page_errors import (
    FORBIDDEN_MESSAGE,
    NOT_FOUND_MESSAGE,
    classify_stats_page_text,
    raise_if_stats_page_error,
)


def test_classify_forbidden():
    html = """
    <html><body>
    <h1>В доступе отказано.</h1>
    <p>У вас недостаточно прав для просмотра этой страницы или выполнения данного действия.</p>
    </body></html>
    """
    assert classify_stats_page_text(html) == "forbidden"


def test_classify_not_found():
    html = """
    <html><body>
    <h1>404. Страница не найдена</h1>
    <p>Страница устарела, была удалена или не существовала вовсе.</p>
    </body></html>
    """
    assert classify_stats_page_text(html) == "not_found"


def test_classify_normal_stats_page():
    html = """
    <div class="k-grid">
      <th>01.07</th><th>Глава 1</th>
    </div>
    """
    assert classify_stats_page_text(html) is None


def test_raise_forbidden():
    with pytest.raises(StatsPageError, match="Нет доступа") as exc_info:
        raise_if_stats_page_error("В доступе отказано. У вас недостаточно прав")
    assert exc_info.value.reason == "forbidden"
    assert str(exc_info.value) == FORBIDDEN_MESSAGE


def test_raise_not_found():
    with pytest.raises(StatsPageError, match="404") as exc_info:
        raise_if_stats_page_error("404. Страница не найдена")
    assert exc_info.value.reason == "not_found"
    assert str(exc_info.value) == NOT_FOUND_MESSAGE


def test_raise_noop_on_normal():
    raise_if_stats_page_error("<div class='k-grid'>Глава 1</div>")
