"""Сервисный слой для UI и будущего API (тонкая обёртка над analyze/storage)."""

from author_today.services.reports import (
    load_funnel_compare,
    load_funnel_steps,
    list_raw_snapshots,
)

__all__ = [
    "load_funnel_steps",
    "load_funnel_compare",
    "list_raw_snapshots",
]
