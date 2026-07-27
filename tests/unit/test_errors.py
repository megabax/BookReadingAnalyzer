"""Доменные ошибки и обёртка pyodbc → StorageError."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from author_today.errors import ConfigError, StorageError
from author_today.storage.mssql.connection import connect
from config.settings import Settings


def test_connect_wraps_pyodbc_error():
    settings = Settings(
        mssql_server="localhost",
        mssql_database="AuthorToday",
        mssql_user="sa",
        mssql_password="x",
    )
    import pyodbc

    with patch(
        "author_today.storage.mssql.connection.pyodbc.connect",
        side_effect=pyodbc.Error("08001", "fake"),
    ):
        with pytest.raises(StorageError, match="подключиться к MS SQL"):
            with connect(settings):
                pass


def test_config_error_is_author_today_error():
    from author_today.errors import AuthorTodayError

    err = ConfigError("нет настроек")
    assert isinstance(err, AuthorTodayError)
    assert str(err) == "нет настроек"
