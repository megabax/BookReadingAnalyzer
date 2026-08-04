"""Доменные ошибки и обёртка pyodbc → StorageError."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from author_today.errors import (
    ConfigError,
    StorageError,
    format_exception_message,
)
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
        side_effect=pyodbc.Error("08001", "[Microsoft] fake connect failure"),
    ):
        with pytest.raises(StorageError, match="подключиться к MS SQL") as exc_info:
            with connect(settings):
                pass
        assert "fake connect failure" in str(exc_info.value)


def test_config_error_is_author_today_error():
    from author_today.errors import AuthorTodayError

    err = ConfigError("нет настроек")
    assert isinstance(err, AuthorTodayError)
    assert str(err) == "нет настроек"


def test_format_exception_message_empty_pyodbc_style():
    class FakePyodbcError(Exception):
        def __str__(self) -> str:
            return "Message:"

    exc = FakePyodbcError("42000", "[Microsoft][ODBC] Duplicate key")
    text = format_exception_message(exc)
    assert "42000" in text
    assert "Duplicate key" in text
    assert "Message:" not in text or "Duplicate key" in text


def test_format_exception_message_cause_chain():
    cause = Exception("42000", "constraint violated")
    wrapped = StorageError("Ошибка при работе с MS SQL")
    wrapped.__cause__ = cause
    text = format_exception_message(wrapped)
    assert "Ошибка при работе с MS SQL" in text
    assert "constraint violated" in text
