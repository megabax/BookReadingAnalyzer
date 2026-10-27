"""Unit-тесты чтения продаж в MssqlReadRepository (mock)."""

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
        mssql_password="x",
    )
    return MssqlReadRepository(settings)


def _mock_connect(cursor: MagicMock):
    conn = MagicMock()
    conn.cursor.return_value = cursor
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    return conn


@patch("author_today.storage.mssql_repo.connect")
def test_list_sale_runs(mock_connect_fn, repo: MssqlReadRepository):
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        (10, date(2026, 10, 1), date(2026, 10, 31), datetime(2026, 10, 20, 12, 0), 3),
    ]
    mock_connect_fn.return_value = _mock_connect(cursor)

    runs = repo.list_sale_runs(172953, limit=10)
    assert len(runs) == 1
    assert runs[0].run_id == 10
    assert runs[0].events_count == 3


@patch("author_today.storage.mssql_repo.connect")
def test_load_sales_period_report(mock_connect_fn, repo: MssqlReadRepository):
    cursor = MagicMock()
    cursor.fetchall.side_effect = [
        [
            (
                1,
                10,
                datetime(2026, 10, 15, 14, 30),
                172953,
                1,
                199.0,
                0.3,
                139.3,
            )
        ],
        [(date(2026, 10, 15), 1, 139.3, 199.0)],
    ]
    mock_connect_fn.return_value = _mock_connect(cursor)

    report = repo.load_sales_period_report(
        172953, date(2026, 10, 1), date(2026, 10, 31)
    )
    assert report.sales_count == 1
    assert report.income_sum == pytest.approx(139.3)
    assert len(report.daily) == 1
    assert report.daily[0].sales_count == 1


def test_work_format_label():
    from author_today.services.sales import work_format_label

    assert work_format_label(1) == "Электронная книга"
    assert work_format_label(2) == "Аудиокнига"
    assert work_format_label(None) == "—"
