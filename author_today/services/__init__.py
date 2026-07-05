"""Сервисный слой для UI и будущего API (тонкая обёртка над analyze/storage)."""

from author_today.services.books import BookOption, load_book_catalog, load_book_data_info
from author_today.services.fetch import FetchResult, fetch_reads_for_period
from author_today.storage.mssql_repo import BookLoadInfo
from author_today.services.reports import (
    load_funnel_compare,
    load_funnel_steps,
    load_read_snapshot,
    list_raw_snapshots,
)

__all__ = [
    "BookLoadInfo",
    "BookOption",
    "FetchResult",
    "fetch_reads_for_period",
    "load_book_catalog",
    "load_book_data_info",
    "load_funnel_steps",
    "load_funnel_compare",
    "load_read_snapshot",
    "list_raw_snapshots",
]
