"""Загрузка статистики с author.today для UI (с паузой на код устройства)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date

from selenium.webdriver.remote.webdriver import WebDriver

import time

from author_today.auth.login_flow import confirmation_code_visible, submit_confirmation_code
from author_today.browser.factory import create_driver
from author_today.domain.models import StatsTable, parse_dd_mm_columns
from author_today.errors import DeviceCodeRequired
from author_today.fetch.periods import needs_monthly_chunks, split_period_into_months
from author_today.pipeline.sync_reads import _auth_provider, _load_and_persist_period
from config.settings import Settings, ensure_data_dirs

# Живые Selenium-сессии между rerun Streamlit (один процесс сервера).
_SESSIONS: dict[str, "FetchSession"] = {}


@dataclass(frozen=True)
class FetchResult:
    book_id: int
    period_start: date
    period_end: date
    chapter_count: int
    day_count: int
    monthly_chunks: int
    saved_mssql: bool
    saved_raw: bool
    table_date_min: date | None = None
    table_date_max: date | None = None


def _raise_device_code_required(hint: str) -> str:
    raise DeviceCodeRequired(hint)


def _result_from_table(
    table: StatsTable,
    *,
    book_id: int,
    period_start: date,
    period_end: date,
    save_mssql: bool,
    save_raw: bool,
) -> FetchResult:
    chunks = split_period_into_months(period_start, period_end)
    parsed_dates = parse_dd_mm_columns(table.dates, period_start)
    return FetchResult(
        book_id=book_id,
        period_start=period_start,
        period_end=period_end,
        chapter_count=len(table.rows),
        day_count=len(table.dates),
        monthly_chunks=len(chunks) if needs_monthly_chunks(period_start, period_end) else 1,
        saved_mssql=save_mssql,
        saved_raw=save_raw,
        table_date_min=min(parsed_dates) if parsed_dates else None,
        table_date_max=max(parsed_dates) if parsed_dates else None,
    )


class FetchSession:
    """
    Интерактивная загрузка: при запросе кода браузер не закрывается,
    UI показывает поле и кнопку «Продолжить».
    """

    def __init__(
        self,
        settings: Settings,
        book_id: int,
        period_start: date,
        period_end: date,
        *,
        save_mssql: bool = True,
        save_raw: bool = False,
        wait_login_seconds: int | None = None,
        session_id: str | None = None,
    ) -> None:
        if period_start > period_end:
            raise ValueError("Начало периода должно быть не позже конца.")
        if save_mssql and not settings.has_mssql():
            raise RuntimeError(
                "MS SQL не настроен. Задайте MSSQL_* в .env или отключите сохранение в БД."
            )

        self.session_id = session_id or uuid.uuid4().hex
        self._settings = replace(settings, book_id=book_id)
        self.book_id = book_id
        self.period_start = period_start
        self.period_end = period_end
        self._save_mssql = save_mssql
        self._save_raw = save_raw
        self._wait_login_seconds = wait_login_seconds
        self._driver: WebDriver | None = None
        self.hint: str | None = None

    @property
    def awaiting_code(self) -> bool:
        return self._driver is not None and self.hint is not None

    def start(self) -> FetchResult:
        """Старт загрузки. При коде — DeviceCodeRequired (драйвер остаётся открытым)."""
        ensure_data_dirs()
        self._driver = create_driver(self._settings)
        self.hint = None
        try:
            result = self._run_loads(code_provider=_raise_device_code_required)
        except DeviceCodeRequired as exc:
            self.hint = exc.hint
            raise
        except Exception:
            self.close()
            raise
        else:
            self.close()
            return result

    def continue_with_code(self, code: str) -> FetchResult:
        """Ввести код в открытую форму и продолжить загрузку."""
        if self._driver is None:
            raise RuntimeError("Нет активной сессии загрузки. Запустите загрузку снова.")

        code = (code or "").strip()
        if not code:
            raise ValueError("Введите код подтверждения.")

        self.hint = None
        try:
            # Сначала довести вход на текущей странице — иначе get(url) уйдёт с формы кода.
            if confirmation_code_visible(self._driver):
                submit_confirmation_code(self._driver, code)
                time.sleep(1)

            auth = _auth_provider(
                self._settings,
                device_code_provider=_raise_device_code_required,
                wait_login_seconds=self._wait_login_seconds,
            )
            auth.ensure_logged_in(self._driver)
            result = self._run_loads(code_provider=_raise_device_code_required)
        except DeviceCodeRequired as exc:
            self.hint = exc.hint
            raise
        except Exception:
            self.close()
            raise
        else:
            self.close()
            return result

    def close(self) -> None:
        driver = self._driver
        self._driver = None
        self.hint = None
        _SESSIONS.pop(self.session_id, None)
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass

    def _run_loads(self, *, code_provider: Callable[[str], str]) -> FetchResult:
        assert self._driver is not None
        auth = _auth_provider(
            self._settings,
            device_code_provider=code_provider,
            wait_login_seconds=self._wait_login_seconds,
        )
        chunks = split_period_into_months(self.period_start, self.period_end)

        if not needs_monthly_chunks(self.period_start, self.period_end):
            table = _load_and_persist_period(
                self._driver,
                auth,
                self._settings,
                self.period_start,
                self.period_end,
                save_raw=self._save_raw,
                save_mssql=self._save_mssql,
            )
        else:
            table = None
            for chunk_start, chunk_end in chunks:
                table = _load_and_persist_period(
                    self._driver,
                    auth,
                    self._settings,
                    chunk_start,
                    chunk_end,
                    save_raw=self._save_raw,
                    save_mssql=self._save_mssql,
                )
            if table is None:
                raise RuntimeError("Не удалось загрузить данные за период.")

        return _result_from_table(
            table,
            book_id=self.book_id,
            period_start=self.period_start,
            period_end=self.period_end,
            save_mssql=self._save_mssql,
            save_raw=self._save_raw,
        )


def register_session(session: FetchSession) -> FetchSession:
    _SESSIONS[session.session_id] = session
    return session


def get_session(session_id: str) -> FetchSession | None:
    return _SESSIONS.get(session_id)


def fetch_reads_for_period(
    settings: Settings,
    book_id: int,
    period_start: date,
    period_end: date,
    *,
    save_mssql: bool = True,
    save_raw: bool = False,
    wait_login_seconds: int | None = None,
    device_code: str | None = None,
) -> FetchResult:
    """
    Однократная загрузка (совместимость).

    Если передан device_code — подставляется при запросе сайта.
    Без кода при запросе сайта — DeviceCodeRequired (драйвер закрывается; для паузы — FetchSession).
    """
    session = FetchSession(
        settings,
        book_id,
        period_start,
        period_end,
        save_mssql=save_mssql,
        save_raw=save_raw,
        wait_login_seconds=wait_login_seconds,
    )
    if device_code and device_code.strip():
        code = device_code.strip()

        def provider(_hint: str) -> str:
            return code

        ensure_data_dirs()
        session._driver = create_driver(session._settings)
        try:
            result = session._run_loads(code_provider=provider)
            session.close()
            return result
        except Exception:
            session.close()
            raise

    try:
        result = session.start()
        return result
    except DeviceCodeRequired:
        session.close()
        raise
