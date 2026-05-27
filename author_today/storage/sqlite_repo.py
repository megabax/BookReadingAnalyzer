from __future__ import annotations

from author_today.domain.models import ReadSnapshot
from author_today.storage.base import ReadRepository


class SqliteReadRepository:
    """SQLite-хранилище (заготовка под будущую реализацию)."""

    def __init__(self, db_path) -> None:
        self.db_path = db_path

    def save_snapshot(self, snapshot: ReadSnapshot) -> int:
        raise NotImplementedError("SQLite-репозиторий будет добавлен позже.")

    def list_runs(self, book_id: int) -> list[dict]:
        raise NotImplementedError("SQLite-репозиторий будет добавлен позже.")
