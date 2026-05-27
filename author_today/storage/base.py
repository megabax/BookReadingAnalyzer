from __future__ import annotations

from typing import Protocol

from author_today.domain.models import ReadSnapshot


class ReadRepository(Protocol):
    """Хранение снимков прочтений."""

    def save_snapshot(self, snapshot: ReadSnapshot) -> int: ...

    def list_runs(self, book_id: int) -> list[dict]: ...
