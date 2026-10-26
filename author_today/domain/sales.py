"""Снимок продаж книги (merchant/dashboard → getdetailstable)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


# ItemType на сайте: 1 = продажа произведения
ITEM_TYPE_WORK = 1

# WorkFormat на сайте
WORK_FORMAT_EBOOK = 1
WORK_FORMAT_AUDIO = 2


@dataclass(frozen=True)
class SaleEvent:
    processed_at: datetime
    book_id: int
    work_format: int | None
    price: float
    commission: float
    author_income: float


@dataclass(frozen=True)
class SaleSnapshot:
    book_id: int
    period_start: date
    period_end: date
    fetched_at: datetime
    events: tuple[SaleEvent, ...]
