"""Детекция страниц ошибки author.today до ожидания Kendo Grid."""

from __future__ import annotations

from author_today.errors import StatsPageError

# Устойчивые фрагменты (вёрстка может меняться вокруг них)
FORBIDDEN_MARKERS = (
    "В доступе отказано",
    "недостаточно прав для просмотра этой страницы",
)
NOT_FOUND_MARKERS = (
    "404. Страница не найдена",
    "Страница не найдена",
    "Страница устарела, была удалена",
)

FORBIDDEN_MESSAGE = (
    "Нет доступа к статистике этой книги (чужая или нет прав). "
    "Загружайте только свои произведения."
)
NOT_FOUND_MESSAGE = (
    "Книга/страница не найдена (404). Проверьте book_id."
)


def classify_stats_page_text(page_text: str) -> str | None:
    """
    Вернуть "forbidden" | "not_found" | None по тексту страницы.

    forbidden проверяется раньше not_found (на случай пересечения формулировок).
    """
    if not page_text:
        return None
    # Нормализуем пробелы для надёжного поиска подстрок
    normalized = " ".join(page_text.split())
    for marker in FORBIDDEN_MARKERS:
        if marker in normalized:
            return "forbidden"
    for marker in NOT_FOUND_MARKERS:
        if marker in normalized:
            return "not_found"
    return None


def raise_if_stats_page_error(page_text: str) -> None:
    """Если страница — отказ/404, бросить StatsPageError."""
    kind = classify_stats_page_text(page_text)
    if kind == "forbidden":
        raise StatsPageError("forbidden", FORBIDDEN_MESSAGE)
    if kind == "not_found":
        raise StatsPageError("not_found", NOT_FOUND_MESSAGE)
