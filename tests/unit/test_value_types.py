"""Тесты value_type / normalize_value_type."""

from __future__ import annotations

import pytest

from author_today.domain.value_types import normalize_value_type, normalize_value_types
from author_today.errors import ConfigError


def test_normalize_value_type_ok():
    assert normalize_value_type("hit") == "hit"
    assert normalize_value_type("time") == "time"
    assert normalize_value_type("avgTime") == "avgTime"


def test_normalize_value_type_rejects_unknown():
    with pytest.raises(ConfigError, match="Неизвестный value_type"):
        normalize_value_type("clicks")


def test_normalize_value_types_order_and_unique():
    assert normalize_value_types(["avgTime", "hit", "hit", "time"]) == (
        "hit",
        "time",
        "avgTime",
    )


def test_normalize_value_types_empty_raises():
    with pytest.raises(ConfigError, match="хотя бы одну метрику"):
        normalize_value_types([])
