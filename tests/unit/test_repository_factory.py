"""Фабрика get_repository / контракт ReadRepository."""

from __future__ import annotations

import pytest

from author_today.storage.factory import get_repository
from author_today.storage.mssql_repo import MssqlReadRepository
from config.settings import Settings


def test_get_repository_requires_mssql():
    settings = Settings(mssql_server=None, mssql_database=None, mssql_connection_string=None)
    with pytest.raises(RuntimeError, match="не настроено"):
        get_repository(settings)


def test_get_repository_returns_mssql_implementation():
    settings = Settings(mssql_server="localhost", mssql_database="AuthorToday", mssql_user="sa", mssql_password="x")
    repo = get_repository(settings)
    assert isinstance(repo, MssqlReadRepository)
