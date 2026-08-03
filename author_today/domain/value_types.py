"""Типы метрик статистики author.today (URL valueType / fetch_runs.value_type)."""

from __future__ import annotations

from author_today.errors import ConfigError

DEFAULT_VALUE_TYPE = "hit"
VALUE_TYPES = frozenset({"hit", "time", "avgTime"})


def normalize_value_type(value: str) -> str:
    """Проверить и вернуть канонический value_type."""
    normalized = (value or "").strip()
    if normalized not in VALUE_TYPES:
        allowed = ", ".join(sorted(VALUE_TYPES))
        raise ConfigError(
            f"Неизвестный value_type={value!r}. Допустимо: {allowed}"
        )
    return normalized
