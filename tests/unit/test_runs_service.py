"""Тесты удаления fetch_run через services/runs."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from author_today.errors import DataNotFoundError
from author_today.services import runs as runs_service
from author_today.storage.mssql_repo import (
    DeleteRunsPreview,
    DeleteRunsResult,
    FetchRunDetail,
    FetchRunReadRow,
)
from config.settings import Settings


def _settings() -> Settings:
    return Settings(
        mssql_server="localhost",
        mssql_database="AuthorToday",
        mssql_user="sa",
        mssql_password="x",
    )


@patch("author_today.services.runs.get_repository")
def test_preview_delete_run_not_found(mock_get_repo):
    repo = MagicMock()
    repo.preview_delete_run.return_value = DeleteRunsPreview(
        run_ids=(),
        runs_count=0,
        reads_count=0,
    )
    mock_get_repo.return_value = repo

    with pytest.raises(DataNotFoundError, match="не найден"):
        runs_service.preview_delete_run(_settings(), 1, 99)


@patch("author_today.services.runs.get_repository")
def test_delete_run_ok(mock_get_repo):
    repo = MagicMock()
    repo.preview_delete_run.return_value = DeleteRunsPreview(
        run_ids=(42,),
        runs_count=1,
        reads_count=10,
    )
    repo.delete_run.return_value = DeleteRunsResult(
        run_ids=(42,),
        runs_count=1,
        reads_count=10,
        deleted_reads=10,
        deleted_runs=1,
    )
    mock_get_repo.return_value = repo

    result = runs_service.delete_run(_settings(), 1, 42)

    assert result.deleted_runs == 1
    assert result.deleted_reads == 10
    repo.delete_run.assert_called_once_with(1, 42)


@patch("author_today.services.runs.get_repository")
def test_load_fetch_run_detail_ok(mock_get_repo):
    from datetime import date, datetime

    detail = FetchRunDetail(
        run_id=42,
        book_id=1,
        period_start=date(2025, 7, 1),
        period_end=date(2025, 7, 31),
        fetched_at=datetime(2026, 6, 1, 12, 0),
        value_type="hit",
        rows=(
            FetchRunReadRow(
                chapter_order=1,
                chapter_name="Глава 1",
                read_date=date(2025, 7, 1),
                metric_value=10,
            ),
        ),
    )
    repo = MagicMock()
    repo.get_fetch_run_detail.return_value = detail
    mock_get_repo.return_value = repo

    loaded = runs_service.load_fetch_run_detail(_settings(), 1, 42)

    assert loaded.run_id == 42
    assert len(loaded.rows) == 1
    repo.get_fetch_run_detail.assert_called_once_with(1, 42)


@patch("author_today.services.runs.get_repository")
def test_load_fetch_run_detail_not_found(mock_get_repo):
    repo = MagicMock()
    repo.get_fetch_run_detail.return_value = None
    mock_get_repo.return_value = repo

    with pytest.raises(DataNotFoundError, match="не найден"):
        runs_service.load_fetch_run_detail(_settings(), 1, 99)
