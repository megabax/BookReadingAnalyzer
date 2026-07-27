"""Фабрика репозитория: единственная точка выбора реализации СУБД."""

from __future__ import annotations

from author_today.errors import ConfigError
from author_today.storage.base import ReadRepository
from author_today.storage.mssql_repo import create_mssql_repository
from config.settings import Settings


def get_repository(settings: Settings) -> ReadRepository:
    """
    Вернуть репозиторий по настройкам.

    Сейчас — только MS SQL. При появлении другой СУБД добавить ветку здесь
    (и класс, реализующий `ReadRepository`), не меняя callers.
    """
    if settings.has_mssql():
        return create_mssql_repository(settings)
    raise ConfigError(
        "Хранилище не настроено. Укажите MSSQL_CONNECTION_STRING или "
        "MSSQL_SERVER + MSSQL_DATABASE в .env (или добавьте другую СУБД в get_repository)."
    )
