from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class StatsTable:
    """Таблица прочтений с сайта (как на странице: даты + строки глав)."""

    dates: list[str] = field(default_factory=list)
    rows: list[dict[str, str | int | None]] = field(default_factory=list)


@dataclass(frozen=True)
class ReadSnapshot:
    """Нормализованный снимок прочтений для хранения и анализа."""

    book_id: int
    period_start: date
    period_end: date
    fetched_at: datetime
    dates: tuple[date, ...]
    chapters: tuple[str, ...]
    values: tuple[tuple[int | None, ...], ...]

    @classmethod
    def from_stats_table(
        cls,
        table: StatsTable,
        *,
        book_id: int,
        period_start: date,
        period_end: date,
        fetched_at: datetime | None = None,
    ) -> ReadSnapshot:
        year = period_end.year
        parsed_dates = tuple(
            date(year, int(d.split(".")[1]), int(d.split(".")[0])) for d in table.dates
        )
        chapters: list[str] = []
        values: list[tuple[int | None, ...]] = []
        for row in table.rows:
            chapters.append(str(row["chapter"]))
            values.append(
                tuple(row.get(d) for d in table.dates)  # type: ignore[misc]
            )
        return cls(
            book_id=book_id,
            period_start=period_start,
            period_end=period_end,
            fetched_at=fetched_at or datetime.now(),
            dates=parsed_dates,
            chapters=tuple(chapters),
            values=tuple(values),
        )

    def to_document(self) -> dict:
        """
        JSON-структура: массив dates, в каждой дате — главы и число просмотров.
        """
        dates_payload = []
        for day_idx, day in enumerate(self.dates):
            chapters_payload = []
            for chapter_idx, chapter in enumerate(self.chapters):
                chapters_payload.append(
                    {
                        "chapter": chapter,
                        "views": self.values[chapter_idx][day_idx],
                    }
                )
            dates_payload.append(
                {
                    "date": day.isoformat(),
                    "chapters": chapters_payload,
                }
            )
        return {
            "book_id": self.book_id,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "fetched_at": self.fetched_at.isoformat(),
            "dates": dates_payload,
        }
