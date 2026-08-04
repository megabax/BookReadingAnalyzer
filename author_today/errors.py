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


def _format_exception_args(exc: BaseException) -> str:
    """Собрать текст из args (pyodbc часто даёт пустой str(exc) = 'Message:')."""
    parts: list[str] = []
    for arg in getattr(exc, "args", ()) or ():
        if arg is None:
            continue
        text = str(arg).strip()
        if not text or text in {"Message:", "Message"}:
            continue
        parts.append(text)
    return "; ".join(parts)


def format_exception_message(exc: BaseException) -> str:
    """
    Человекочитаемое сообщение для UI/логов.
    Учитывает цепочку __cause__ и «пустые» pyodbc.Error.
    """
    chunks: list[str] = []
    current: BaseException | None = exc
    seen: set[int] = set()

    while current is not None and id(current) not in seen:
        seen.add(id(current))
        name = type(current).__name__
        primary = str(current).strip()
        from_args = _format_exception_args(current)

        if primary and primary not in {"Message:", "Message"}:
            text = primary
        elif from_args:
            text = from_args
        else:
            text = repr(current.args) if getattr(current, "args", None) else "(нет текста)"

        if not text.startswith(name):
            chunks.append(f"{name}: {text}")
        else:
            chunks.append(text)

        current = current.__cause__

    return " ← ".join(chunks) if chunks else type(exc).__name__
