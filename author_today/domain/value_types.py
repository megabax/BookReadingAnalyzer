"""Типы метрик статистики author.today (URL valueType / fetch_runs.value_type)."""

from __future__ import annotations

from collections.abc import Iterable

from author_today.errors import ConfigError

DEFAULT_VALUE_TYPE = "hit"
VALUE_TYPES = frozenset({"hit", "time", "avgTime"})
VALUE_TYPE_ORDER = ("hit", "time", "avgTime")
VALUE_TYPE_LABELS = {
    "hit": "Просмотры (hit)",
    "time": "Время чтения (time)",
    "avgTime": "Среднее время (avgTime)",
}


def normalize_value_type(value: str) -> str:
    """Проверить и вернуть канонический value_type."""
    normalized = (value or "").strip()
    if normalized not in VALUE_TYPES:
        allowed = ", ".join(VALUE_TYPE_ORDER)
        raise ConfigError(
            f"Неизвестный value_type={value!r}. Допустимо: {allowed}"
        )
    return normalized


def normalize_value_types(values: Iterable[str]) -> tuple[str, ...]:
    """Уникальный упорядоченный список метрик (порядок VALUE_TYPE_ORDER)."""
    selected = {normalize_value_type(v) for v in values}
    if not selected:
        raise ConfigError("Укажите хотя бы одну метрику (hit / time / avgTime)")
    return tuple(v for v in VALUE_TYPE_ORDER if v in selected)
