from __future__ import annotations

import pyodbc

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


def connect(settings: Settings) -> pyodbc.Connection:
    return pyodbc.connect(build_connection_string(settings), autocommit=False)
