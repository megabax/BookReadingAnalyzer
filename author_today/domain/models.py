from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

# Значение метрики ячейки (hit / time / avgTime); в БД — DECIMAL(12,2).
MetricValue = float

# read_date -> site_chapter_order -> (chapter_name, metric_value)
DailyMatrix = dict[date, dict[int, tuple[str, MetricValue]]]


def coerce_metric_value(value: object | None) -> MetricValue | None:
    """int / Decimal / float / str → float; None остаётся None."""
    if value is None:
        return None
    return float(value)


def parse_dd_mm_columns(headers: list[str], period_start: date) -> tuple[date, ...]:
    """Разобрать заголовки Kendo DD.MM; год увеличивается при «откате» месяца."""
    if not headers:
        return ()
    year = period_start.year
    prev_month = int(headers[0].split(".")[1])
    parsed: list[date] = []
    for header in headers:
        day_s, month_s = header.split(".")
        day, month = int(day_s), int(month_s)
        if month < prev_month:
            year += 1
        prev_month = month
        parsed.append(date(year, month, day))
    return tuple(parsed)


@dataclass
class StatsTable:
    """Таблица прочтений с сайта (как на странице: даты + строки глав)."""

    dates: list[str] = field(default_factory=list)
    rows: list[dict[str, str | int | float | None]] = field(default_factory=list)


@dataclass(frozen=True)
class ReadSnapshot:
    """Нормализованный снимок прочтений для хранения и анализа."""

    book_id: int
    period_start: date
    period_end: date
    fetched_at: datetime
    dates: tuple[date, ...]
    chapters: tuple[str, ...]
    values: tuple[tuple[MetricValue | None, ...], ...]
    chapter_orders: tuple[int, ...] | None = None

    def site_chapter_order(self, chapter_index: int) -> int:
        if self.chapter_orders is not None:
            return self.chapter_orders[chapter_index]
        return chapter_index + 1

    def chapter_totals(self) -> list[tuple[int, str, MetricValue]]:
        """(chapter_order, chapter_name, sum metric_value) для воронки."""
        return [
            (
                self.site_chapter_order(idx),
                chapter,
                float(sum(v or 0 for v in self.values[idx])),
            )
            for idx, chapter in enumerate(self.chapters)
        ]

    def daily_matrix(self) -> DailyMatrix:
        """Дневная матрица для сравнения периодов."""
        matrix: DailyMatrix = {}
        for day_idx, read_date in enumerate(self.dates):
            by_order: dict[int, tuple[str, MetricValue]] = {}
            for ch_idx, chapter in enumerate(self.chapters):
                by_order[self.site_chapter_order(ch_idx)] = (
                    chapter,
                    float(self.values[ch_idx][day_idx] or 0),
                )
            matrix[read_date] = by_order
        return matrix

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
        parsed_dates = parse_dd_mm_columns(table.dates, period_start)
        chapters: list[str] = []
        values: list[tuple[MetricValue | None, ...]] = []
        for row in table.rows:
            chapters.append(str(row["chapter"]))
            values.append(
                tuple(coerce_metric_value(row.get(d)) for d in table.dates)
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

    @classmethod
    def from_json(cls, path: Path | str) -> ReadSnapshot:
        """Загрузить снимок из JSON (контракт data/raw, тесты)."""
        return cls.from_document(json.loads(Path(path).read_text(encoding="utf-8")))

    @classmethod
    def from_document(cls, data: dict) -> ReadSnapshot:
        dates = tuple(date.fromisoformat(str(d["date"])[:10]) for d in data.get("dates", []))
        if not data.get("dates"):
            return cls(
                book_id=int(data["book_id"]),
                period_start=date.fromisoformat(str(data["period_start"])[:10]),
                period_end=date.fromisoformat(str(data["period_end"])[:10]),
                fetched_at=datetime.fromisoformat(data["fetched_at"]),
                dates=(),
                chapters=(),
                values=(),
            )

        chapters = tuple(str(ch["chapter"]) for ch in data["dates"][0]["chapters"])
        values: list[tuple[MetricValue | None, ...]] = []
        for ch_idx in range(len(chapters)):
            row: list[MetricValue | None] = []
            for day in data["dates"]:
                ch = day["chapters"][ch_idx]
                row.append(coerce_metric_value(ch.get("views")))
            values.append(tuple(row))

        return cls(
            book_id=int(data["book_id"]),
            period_start=date.fromisoformat(str(data["period_start"])[:10]),
            period_end=date.fromisoformat(str(data["period_end"])[:10]),
            fetched_at=datetime.fromisoformat(data["fetched_at"]),
            dates=dates,
            chapters=chapters,
            values=tuple(values),
        )

    @classmethod
    def from_aggregated_rows(
        cls,
        *,
        book_id: int,
        period_start: date,
        period_end: date,
        fetched_at: datetime,
        rows: list[tuple[date, int, str, MetricValue]],
    ) -> ReadSnapshot:
        """Собрать снимок из строк (read_date, chapter_order, chapter_name, metric_value)."""
        if not rows:
            return cls(
                book_id=book_id,
                period_start=period_start,
                period_end=period_end,
                fetched_at=fetched_at,
                dates=(),
                chapters=(),
                values=(),
            )

        dates = tuple(sorted({row[0] for row in rows}))
        date_index = {d: idx for idx, d in enumerate(dates)}
        orders = sorted({row[1] for row in rows})
        order_index = {order: idx for idx, order in enumerate(orders)}
        names: dict[int, str] = {}
        for _read_date, order, name, _metric in rows:
            names[order] = name

        values_grid: list[list[MetricValue]] = [[0.0] * len(dates) for _ in orders]
        for read_date, order, _name, metric in rows:
            values_grid[order_index[order]][date_index[read_date]] = float(metric)

        return cls(
            book_id=book_id,
            period_start=period_start,
            period_end=period_end,
            fetched_at=fetched_at,
            dates=dates,
            chapters=tuple(names[order] for order in orders),
            values=tuple(tuple(row) for row in values_grid),
            chapter_orders=tuple(orders),
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
