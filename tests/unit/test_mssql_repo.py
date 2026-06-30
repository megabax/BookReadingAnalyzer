"""Unit-тесты методов чтения/удаления в MssqlReadRepository (mock pyodbc)."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from author_today.storage.mssql_repo import MssqlReadRepository
from config.settings import Settings


@pytest.fixture
def repo() -> MssqlReadRepository:
    settings = Settings(
        mssql_server="localhost",
        mssql_database="AutorToday",
        mssql_user="sa",
        mssql_password="secret",
    )
    return MssqlReadRepository(settings)


def _mock_connect(fetchall_results: list[list] | None = None, fetchone_results: list | None = None):
    cursor = MagicMock()
    if fetchall_results is not None:
        cursor.fetchall.side_effect = fetchall_results
    if fetchone_results is not None:
        cursor.fetchone.side_effect = fetchone_results
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor


@patch("author_today.storage.mssql_repo.connect")
def test_aggregate_chapter_views(mock_connect_fn, repo: MssqlReadRepository):
    conn, cursor = _mock_connect(fetchall_results=[[(1, "Глава 1", 100), (2, "Глава 2", 50)]])
    mock_connect_fn.return_value.__enter__.return_value = conn

    rows = repo.aggregate_chapter_views(323389, date(2025, 7, 1), date(2025, 7, 31))

    assert rows == [(1, "Глава 1", 100), (2, "Глава 2", 50)]
    sql = cursor.execute.call_args[0][0]
    assert "SUM(COALESCE(cr.views, 0))" in sql
    assert cursor.execute.call_args[0][1:] == (323389, date(2025, 7, 1), date(2025, 7, 31))


@patch("author_today.storage.mssql_repo.connect")
def test_daily_chapter_matrix(mock_connect_fn, repo: MssqlReadRepository):
    conn, cursor = _mock_connect(
        fetchall_results=[
            [
                (date(2025, 7, 1), 1, "Глава 1", 10),
                (date(2025, 7, 1), 2, "Глава 2", 5),
            ]
        ]
    )
    mock_connect_fn.return_value.__enter__.return_value = conn

    matrix = repo.daily_chapter_matrix(323389, date(2025, 7, 1), date(2025, 7, 1))

    assert matrix[date(2025, 7, 1)][1] == ("Глава 1", 10)
    assert matrix[date(2025, 7, 1)][2] == ("Глава 2", 5)


@patch("author_today.storage.mssql_repo.connect")
def test_preview_delete_runs_by_fetched_at(mock_connect_fn, repo: MssqlReadRepository):
    conn, cursor = _mock_connect(
        fetchall_results=[[(10,), (11,)]],
        fetchone_results=[(42,)],
    )
    mock_connect_fn.return_value.__enter__.return_value = conn

    preview = repo.preview_delete_runs_by_fetched_at(
        323389,
        datetime(2026, 6, 2, 9, 0, 0),
        datetime(2026, 6, 2, 10, 0, 0),
    )

    assert preview.run_ids == (10, 11)
    assert preview.runs_count == 2
    assert preview.reads_count == 42
    assert cursor.execute.call_count == 2


@patch("author_today.storage.mssql_repo.connect")
def test_delete_runs_by_fetched_at_empty(mock_connect_fn, repo: MssqlReadRepository):
    conn, cursor = _mock_connect(fetchall_results=[[]], fetchone_results=[(0,)])
    mock_connect_fn.return_value.__enter__.return_value = conn

    result = repo.delete_runs_by_fetched_at(
        323389,
        datetime(2026, 6, 2, 9, 0, 0),
        datetime(2026, 6, 2, 10, 0, 0),
    )

    assert result.deleted_runs == 0
    assert result.deleted_reads == 0
    conn.commit.assert_not_called()


@patch("author_today.storage.mssql_repo.connect")
def test_delete_runs_by_fetched_at_deletes(mock_connect_fn, repo: MssqlReadRepository):
    preview_conn, preview_cursor = _mock_connect(fetchall_results=[[(7,)]], fetchone_results=[(3,)])
    delete_conn, delete_cursor = _mock_connect()
    delete_cursor.rowcount = 3
    mock_connect_fn.return_value.__enter__.side_effect = [preview_conn, delete_conn]

    result = repo.delete_runs_by_fetched_at(
        323389,
        datetime(2026, 6, 2, 9, 0, 0),
        datetime(2026, 6, 2, 10, 0, 0),
    )

    assert result.runs_count == 1
    assert result.deleted_reads == 3
    assert delete_cursor.execute.call_count == 2
    delete_conn.commit.assert_called_once()
