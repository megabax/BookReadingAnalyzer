from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator

import pyodbc

from author_today.errors import StorageError
from config.settings import Settings


def build_connection_string(settings: Settings) -> str:
    if settings.mssql_connection_string:
        return settings.mssql_connection_string

    parts = [
        f"DRIVER={{{settings.mssql_driver}}}",
        f"SERVER={settings.mssql_server}",
        f"DATABASE={settings.mssql_database}",
    ]
    if settings.mssql_trusted_connection:
        parts.append("Trusted_Connection=yes")
    else:
        parts.append(f"UID={settings.mssql_user}")
        parts.append(f"PWD={settings.mssql_password}")
    if settings.mssql_trust_server_certificate:
        parts.append("TrustServerCertificate=yes")
    return ";".join(parts)


@contextmanager
def connect(settings: Settings) -> Iterator[pyodbc.Connection]:
    """Открыть соединение; pyodbc.Error → StorageError."""
    try:
        conn = pyodbc.connect(build_connection_string(settings), autocommit=False)
    except pyodbc.Error as exc:
        raise StorageError(
            "Не удалось подключиться к MS SQL. Проверьте MSSQL_* в .env и что сервер запущен."
        ) from exc
    try:
        yield conn
    except pyodbc.Error as exc:
        raise StorageError(
            "Ошибка при работе с MS SQL. Проверьте схему БД, права доступа и логи сервера."
        ) from exc
    finally:
        try:
            conn.close()
        except pyodbc.Error:
            pass
