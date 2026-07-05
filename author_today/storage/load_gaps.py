"""Проверка пропусков дней в загрузках (fetch_runs vs chapter_reads)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class RunGapReport:
    run_id: int
    book_id: int
    book_title: str | None
    period_start: date
    period_end: date
    fetched_at: date | str
    expected_days: int
    actual_days: int
    missing_days: tuple[date, ...]

    @property
    def has_gaps(self) -> bool:
        return bool(self.missing_days)


def iter_period_days(period_start: date, period_end: date):
    current = period_start
    while current <= period_end:
        yield current
        current += timedelta(days=1)


def find_missing_days(
    period_start: date,
    period_end: date,
    actual_dates: set[date],
) -> list[date]:
    """Дни из [period_start, period_end], которых нет в actual_dates."""
    if period_start > period_end:
        return []
    missing: list[date] = []
    for day in iter_period_days(period_start, period_end):
        if day not in actual_dates:
            missing.append(day)
    return missing


def format_date_ranges(dates: list[date] | tuple[date, ...]) -> str:
    """Сжать список дат в диапазоны: 2026-06-01 .. 2026-06-05, 2026-06-10."""
    if not dates:
        return "—"
    ordered = sorted(dates)
    ranges: list[tuple[date, date]] = []
    start = end = ordered[0]
    for day in ordered[1:]:
        if day == end + timedelta(days=1):
            end = day
        else:
            ranges.append((start, end))
            start = end = day
    ranges.append((start, end))

    parts: list[str] = []
    for range_start, range_end in ranges:
        if range_start == range_end:
            parts.append(range_start.isoformat())
        else:
            parts.append(f"{range_start.isoformat()} .. {range_end.isoformat()}")
    return ", ".join(parts)
