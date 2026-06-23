"""Общие фикстуры pytest."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from author_today.domain.models import ReadSnapshot, StatsTable

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def minimal_snapshot_path(fixtures_dir: Path) -> Path:
    return fixtures_dir / "snapshot_minimal.json"


@pytest.fixture
def minimal_snapshot(minimal_snapshot_path: Path) -> ReadSnapshot:
    return read_snapshot_from_json(minimal_snapshot_path)


def read_snapshot_from_json(path: Path) -> ReadSnapshot:
    """Собрать ReadSnapshot из JSON-файла (контракт data/raw)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    dates = tuple(date.fromisoformat(str(d["date"])[:10]) for d in data["dates"])
    if not data["dates"]:
        return ReadSnapshot(
            book_id=int(data["book_id"]),
            period_start=date.fromisoformat(data["period_start"]),
            period_end=date.fromisoformat(data["period_end"]),
            fetched_at=datetime.fromisoformat(data["fetched_at"]),
            dates=(),
            chapters=(),
            values=(),
        )

    chapters = tuple(str(ch["chapter"]) for ch in data["dates"][0]["chapters"])
    values: list[tuple[int | None, ...]] = []
    for ch_idx in range(len(chapters)):
        row: list[int | None] = []
        for day in data["dates"]:
            ch = day["chapters"][ch_idx]
            v = ch.get("views")
            row.append(int(v) if v is not None else None)
        values.append(tuple(row))

    return ReadSnapshot(
        book_id=int(data["book_id"]),
        period_start=date.fromisoformat(str(data["period_start"])[:10]),
        period_end=date.fromisoformat(str(data["period_end"])[:10]),
        fetched_at=datetime.fromisoformat(data["fetched_at"]),
        dates=dates,
        chapters=chapters,
        values=tuple(values),
    )
