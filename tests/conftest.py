"""Общие фикстуры pytest."""

from __future__ import annotations

from pathlib import Path

import pytest

from author_today.domain.models import ReadSnapshot

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def minimal_snapshot_path(fixtures_dir: Path) -> Path:
    return fixtures_dir / "snapshot_minimal.json"


@pytest.fixture
def minimal_snapshot(minimal_snapshot_path: Path) -> ReadSnapshot:
    return ReadSnapshot.from_json(minimal_snapshot_path)
