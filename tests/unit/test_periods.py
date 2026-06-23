"""Тесты разбиения периода на месяцы."""

from __future__ import annotations

from datetime import date

import pytest

from author_today.fetch.periods import needs_monthly_chunks, split_period_into_months


def test_single_month():
    chunks = split_period_into_months(date(2025, 7, 1), date(2025, 7, 31))
    assert chunks == [(date(2025, 7, 1), date(2025, 7, 31))]
    assert needs_monthly_chunks(date(2025, 7, 1), date(2025, 7, 31)) is False


def test_cross_month():
    chunks = split_period_into_months(date(2025, 7, 15), date(2025, 8, 10))
    assert chunks == [
        (date(2025, 7, 15), date(2025, 7, 31)),
        (date(2025, 8, 1), date(2025, 8, 10)),
    ]
    assert needs_monthly_chunks(date(2025, 7, 15), date(2025, 8, 10)) is True


def test_cross_year():
    chunks = split_period_into_months(date(2025, 12, 1), date(2026, 1, 31))
    assert chunks == [
        (date(2025, 12, 1), date(2025, 12, 31)),
        (date(2026, 1, 1), date(2026, 1, 31)),
    ]


def test_single_day():
    chunks = split_period_into_months(date(2025, 2, 14), date(2025, 2, 14))
    assert chunks == [(date(2025, 2, 14), date(2025, 2, 14))]


def test_invalid_period_raises():
    with pytest.raises(ValueError, match="period_end"):
        split_period_into_months(date(2025, 8, 1), date(2025, 7, 1))
