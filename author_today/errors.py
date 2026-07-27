"""Доменные исключения для CLI/UI (без сырого pyodbc в точках входа)."""

from __future__ import annotations


class AuthorTodayError(Exception):
    """Базовое исключение приложения — ловить на границе CLI/UI."""


class ConfigError(AuthorTodayError):
    """Неверные или отсутствующие настройки (.env, флаги, параметры запуска)."""


class DataNotFoundError(AuthorTodayError):
    """Нет данных за период / нет нужной главы / пустой результат отчёта."""


class AuthError(AuthorTodayError):
    """Ошибка входа на author.today (форма, таймаут, неверный пароль)."""


class StorageError(AuthorTodayError):
    """Ошибка хранилища (MS SQL / будущая СУБД); оборачивает драйвер БД."""


class DeviceCodeRequired(AuthorTodayError):
    """Сайт запросил код устройства / 2FA; браузерная сессия должна остаться открытой."""

    def __init__(self, hint: str) -> None:
        self.hint = hint
        super().__init__(hint)
