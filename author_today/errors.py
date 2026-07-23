"""Доменные исключения для CLI/UI (без сырого pyodbc в точках входа)."""

from __future__ import annotations


class AuthorTodayError(Exception):
    """Базовое исключение приложения."""


class DeviceCodeRequired(AuthorTodayError):
    """Сайт запросил код устройства / 2FA; браузерная сессия должна остаться открытой."""

    def __init__(self, hint: str) -> None:
        self.hint = hint
        super().__init__(hint)
