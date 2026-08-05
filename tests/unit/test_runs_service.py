"""Тесты удаления fetch_run через services/runs."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from author_today.errors import DataNotFoundError
from author_today.services import runs as runs_service
from author_today.storage.mssql_repo import DeleteRunsPreview, DeleteRunsResult
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
