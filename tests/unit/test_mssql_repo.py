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
        mssql_database="AuthorToday",
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
def test_load_snapshot(mock_connect_fn, repo: MssqlReadRepository):
    conn, cursor = _mock_connect(
        fetchall_results=[
            [
                (date(2025, 7, 1), 1, "Глава 1", 100),
                (date(2025, 7, 1), 2, "Глава 2", 50),
            ]
        ],
        fetchone_results=[(datetime(2026, 6, 1, 12, 0, 0),)],
    )
    mock_connect_fn.return_value.__enter__.return_value = conn

    snapshot = repo.load_snapshot(323389, date(2025, 7, 1), date(2025, 7, 31))

    assert snapshot.book_id == 323389
    assert snapshot.value_type == "hit"
    assert snapshot.chapter_orders == (1, 2)
    assert snapshot.chapter_totals() == [(1, "Глава 1", 100), (2, "Глава 2", 50)]
    assert cursor.execute.call_count == 2
    first_sql = cursor.execute.call_args_list[0].args[0]
    assert "fr.value_type = ?" in first_sql
    assert cursor.execute.call_args_list[0].args[1] == (323389, "hit", date(2025, 7, 1), date(2025, 7, 31))


@patch("author_today.storage.mssql_repo.connect")
def test_load_snapshot_filters_value_type(mock_connect_fn, repo: MssqlReadRepository):
    conn, cursor = _mock_connect(
        fetchall_results=[[]],
        fetchone_results=[(None,)],
    )
    mock_connect_fn.return_value.__enter__.return_value = conn

    snapshot = repo.load_snapshot(
        323389,
        date(2025, 7, 1),
        date(2025, 7, 31),
        value_type="time",
    )

    assert snapshot.value_type == "time"
    assert cursor.execute.call_args_list[0].args[1][1] == "time"


@patch("author_today.storage.mssql_repo.connect")
def test_aggregate_chapter_views(mock_connect_fn, repo: MssqlReadRepository):
    conn, cursor = _mock_connect(
        fetchall_results=[[(date(2025, 7, 1), 1, "Глава 1", 100), (date(2025, 7, 1), 2, "Глава 2", 50)]],
        fetchone_results=[(datetime(2026, 6, 1, 12, 0, 0),)],
    )
    mock_connect_fn.return_value.__enter__.return_value = conn

    rows = repo.aggregate_chapter_views(323389, date(2025, 7, 1), date(2025, 7, 31))

    assert rows == [(1, "Глава 1", 100), (2, "Глава 2", 50)]


@patch("author_today.storage.mssql_repo.connect")
def test_daily_chapter_matrix(mock_connect_fn, repo: MssqlReadRepository):
    conn, cursor = _mock_connect(
        fetchall_results=[
            [
                (date(2025, 7, 1), 1, "Глава 1", 10),
                (date(2025, 7, 1), 2, "Глава 2", 5),
            ]
        ],
        fetchone_results=[(datetime(2026, 6, 1, 12, 0, 0),)],
    )
    mock_connect_fn.return_value.__enter__.return_value = conn

    matrix = repo.daily_chapter_matrix(323389, date(2025, 7, 1), date(2025, 7, 1))

    assert matrix[date(2025, 7, 1)][1] == ("Глава 1", 10)
    assert matrix[date(2025, 7, 1)][2] == ("Глава 2", 5)


@patch("author_today.storage.mssql_repo.connect")
def test_preview_delete_run(mock_connect_fn, repo: MssqlReadRepository):
    conn, cursor = _mock_connect(
        fetchall_results=[[(42,)]],
        fetchone_results=[(120,)],
    )
    mock_connect_fn.return_value.__enter__.return_value = conn

    preview = repo.preview_delete_run(172953, 42)

    assert preview.run_ids == (42,)
    assert preview.runs_count == 1
    assert preview.reads_count == 120
    sql = cursor.execute.call_args_list[0].args[0]
    assert "fr.id = ?" in sql


@patch("author_today.storage.mssql_repo.connect")
def test_delete_run_deletes(mock_connect_fn, repo: MssqlReadRepository):
    preview_conn, _preview_cursor = _mock_connect(
        fetchall_results=[[(42,)]],
        fetchone_results=[(7,)],
    )
    delete_conn, delete_cursor = _mock_connect()
    delete_cursor.rowcount = 7
    mock_connect_fn.return_value.__enter__.side_effect = [preview_conn, delete_conn]

    result = repo.delete_run(172953, 42)

    assert result.runs_count == 1
    assert result.run_ids == (42,)
    assert result.deleted_reads == 7
    assert delete_cursor.execute.call_count == 2
    delete_conn.commit.assert_called_once()


@patch("author_today.storage.mssql_repo.connect")
def test_preview_delete_runs_by_period(mock_connect_fn, repo: MssqlReadRepository):
    conn, cursor = _mock_connect(
        fetchall_results=[[(20,), (21,)]],
        fetchone_results=[(100,)],
    )
    mock_connect_fn.return_value.__enter__.return_value = conn

    preview = repo.preview_delete_runs_by_period(
        172953,
        date(2026, 6, 1),
        date(2026, 6, 30),
    )

    assert preview.run_ids == (20, 21)
    assert preview.runs_count == 2
    assert preview.reads_count == 100
    assert cursor.execute.call_count == 2


@patch("author_today.storage.mssql_repo.connect")
def test_delete_runs_by_period_deletes(mock_connect_fn, repo: MssqlReadRepository):
    preview_conn, preview_cursor = _mock_connect(fetchall_results=[[(9,)]], fetchone_results=[(5,)])
    delete_conn, delete_cursor = _mock_connect()
    delete_cursor.rowcount = 5
    mock_connect_fn.return_value.__enter__.side_effect = [preview_conn, delete_conn]

    result = repo.delete_runs_by_period(
        172953,
        date(2026, 6, 1),
        date(2026, 6, 30),
    )

    assert result.runs_count == 1
    assert result.deleted_reads == 5
    assert delete_cursor.execute.call_count == 2
    delete_conn.commit.assert_called_once()


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


@patch("author_today.storage.mssql_repo.connect")
def test_get_book_load_info(mock_connect_fn, repo: MssqlReadRepository):
    list_conn, list_cursor = _mock_connect(
        fetchall_results=[
            [
                (
                    10,
                    172953,
                    date(2025, 7, 1),
                    date(2025, 7, 31),
                    datetime(2026, 6, 1, 12, 0),
                    "hit",
                ),
            ]
        ],
    )
    list_cursor.description = [
        ("id",),
        ("work_id",),
        ("period_start",),
        ("period_end",),
        ("fetched_at",),
        ("value_type",),
    ]
    span_conn, span_cursor = _mock_connect(fetchone_results=[(date(2025, 7, 1), date(2025, 7, 31))])
    mock_connect_fn.return_value.__enter__.side_effect = [list_conn, span_conn]

    info = repo.get_book_load_info(172953)

    assert info.book_id == 172953
    assert info.read_date_min == date(2025, 7, 1)
    assert info.read_date_max == date(2025, 7, 31)
    assert len(info.runs) == 1
    assert info.runs[0].period_start == date(2025, 7, 1)
    assert info.runs[0].value_type == "hit"
    span_sql = span_cursor.execute.call_args.args[0]
    assert "fr.value_type = ?" in span_sql


@patch("author_today.storage.mssql_repo.connect")
def test_update_book_title(mock_connect_fn, repo: MssqlReadRepository):
    conn, cursor = _mock_connect()
    cursor.rowcount = 1
    mock_connect_fn.return_value.__enter__.return_value = conn

    assert repo.update_book_title(172953, "Рыба") is True

    sql, params = cursor.execute.call_args.args
    assert "UPDATE dbo.books" in sql
    assert params == ("Рыба", 172953)
    conn.commit.assert_called_once()


@patch("author_today.storage.mssql_repo.connect")
def test_update_book_title_missing(mock_connect_fn, repo: MssqlReadRepository):
    conn, cursor = _mock_connect()
    cursor.rowcount = 0
    mock_connect_fn.return_value.__enter__.return_value = conn

    assert repo.update_book_title(999, None) is False

