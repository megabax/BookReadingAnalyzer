"""Разбиение периода загрузки на календарные месяцы."""

from __future__ import annotations

import calendar
from datetime import date, timedelta


def split_period_into_months(period_start: date, period_end: date) -> list[tuple[date, date]]:
    """Вернуть подпериоды [start, end], каждый в пределах одного календарного месяца."""
    if period_end < period_start:
        raise ValueError(
            f"period_end ({period_end}) не может быть раньше period_start ({period_start})"
        )

    chunks: list[tuple[date, date]] = []
    cursor = period_start
    while cursor <= period_end:
        last_day = calendar.monthrange(cursor.year, cursor.month)[1]
        month_end = date(cursor.year, cursor.month, last_day)
        chunk_end = min(month_end, period_end)
        chunks.append((cursor, chunk_end))
        if chunk_end >= period_end:
            break
        cursor = chunk_end + timedelta(days=1)
    return chunks


def needs_monthly_chunks(period_start: date, period_end: date) -> bool:
    """True, если период длиннее одного календарного месяца."""
    return len(split_period_into_months(period_start, period_end)) > 1
