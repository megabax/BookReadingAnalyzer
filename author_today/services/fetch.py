"""Загрузка статистики с author.today для UI (фон, прогресс, пауза на код)."""

from __future__ import annotations

import queue
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date
from typing import Literal

from selenium.webdriver.remote.webdriver import WebDriver

from author_today.auth.login_flow import confirmation_code_visible, submit_confirmation_code
from author_today.browser.factory import create_driver
from author_today.domain.models import StatsTable, parse_dd_mm_columns
from author_today.domain.value_types import (
    DEFAULT_VALUE_TYPE,
    normalize_value_types,
)
from author_today.errors import ConfigError, DeviceCodeRequired, format_exception_message
from author_today.fetch.periods import needs_monthly_chunks, split_period_into_months
from author_today.pipeline.sync_reads import _auth_provider, _load_and_persist_period
from config.settings import Settings, ensure_data_dirs

FetchStatus = Literal["idle", "running", "awaiting_code", "done", "error", "cancelled"]

# Синхронные сессии (совместимость / тесты).
_SESSIONS: dict[str, "FetchSession"] = {}
# Фоновые задачи UI.
_JOBS: dict[str, "FetchJob"] = {}
_jobs_lock = threading.Lock()


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
    value_types: tuple[str, ...] = ("hit",)


@dataclass
class FetchProgress:
    """Снимок прогресса фоновой загрузки (потокобезопасная копия для UI)."""

    status: FetchStatus = "idle"
    stage: str = ""
    book_id: int = 0
    period_start: date | None = None
    period_end: date | None = None
    current_chunk: int = 0
    total_chunks: int = 1
    hint: str | None = None
    error: str | None = None
    result: FetchResult | None = None
    value_type: str | None = None
    value_types: tuple[str, ...] = ()

    @property
    def fraction(self) -> float:
        if self.status == "done":
            return 1.0
        if self.status in ("idle", "error", "cancelled"):
            return 0.0
        if self.status == "awaiting_code":
            # Авторизация почти в начале.
            return 0.08
        total = max(1, self.total_chunks)
        # current_chunk — номер порции в работе (1..N); до первой — 0.
        if self.current_chunk <= 0:
            return 0.05
        # Середина текущей порции: (i - 0.5) / N, завершённые — i/N после апдейта stage.
        return min(0.99, self.current_chunk / total)

    @property
    def is_active(self) -> bool:
        return self.status in ("running", "awaiting_code")

    @property
    def chunk_label(self) -> str:
        total = max(1, self.total_chunks)
        current = max(0, self.current_chunk)
        return f"{current}/{total}"


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
    value_types: tuple[str, ...] = ("hit",),
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
        value_types=value_types,
    )


class FetchSession:
    """
    Синхронная загрузка: при запросе кода — DeviceCodeRequired, драйвер остаётся открытым.
    Для UI предпочтителен FetchJob (фон + прогресс).
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
        on_progress: Callable[[str, int, int], None] | None = None,
        value_types: tuple[str, ...] | list[str] | None = None,
    ) -> None:
        if period_start > period_end:
            raise ValueError("Начало периода должно быть не позже конца.")
        if save_mssql and not settings.has_mssql():
            raise ConfigError(
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
        self._on_progress = on_progress
        self._value_types = normalize_value_types(
            value_types
            if value_types is not None
            else (settings.value_type or DEFAULT_VALUE_TYPE,)
        )
        self._driver: WebDriver | None = None
        self.hint: str | None = None

    @property
    def awaiting_code(self) -> bool:
        return self._driver is not None and self.hint is not None

    def start(self) -> FetchResult:
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
        if self._driver is None:
            raise RuntimeError("Нет активной сессии загрузки. Запустите загрузку снова.")

        code = (code or "").strip()
        if not code:
            raise ValueError("Введите код подтверждения.")

        self.hint = None
        try:
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

    def _emit(self, stage: str, current_chunk: int, total_chunks: int) -> None:
        if self._on_progress:
            self._on_progress(stage, current_chunk, total_chunks)

    def _run_loads(self, *, code_provider: Callable[[str], str]) -> FetchResult:
        assert self._driver is not None
        auth = _auth_provider(
            self._settings,
            device_code_provider=code_provider,
            wait_login_seconds=self._wait_login_seconds,
        )
        month_chunks = split_period_into_months(self.period_start, self.period_end)
        if not needs_monthly_chunks(self.period_start, self.period_end):
            month_chunks = [(self.period_start, self.period_end)]
        total = len(month_chunks) * len(self._value_types)
        step = 0
        table: StatsTable | None = None

        for metric in self._value_types:
            settings = replace(self._settings, value_type=metric)
            for chunk_start, chunk_end in month_chunks:
                step += 1
                self._emit(
                    f"[{metric}] Загрузка {chunk_start} — {chunk_end} "
                    f"(шаг {step}/{total})…",
                    step,
                    total,
                )
                table = _load_and_persist_period(
                    self._driver,
                    auth,
                    settings,
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
            value_types=self._value_types,
        )


class FetchJob:
    """Фоновая загрузка в отдельном потоке: прогресс, пауза на код, отмена."""

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
        job_id: str | None = None,
        value_types: tuple[str, ...] | list[str] | None = None,
    ) -> None:
        if period_start > period_end:
            raise ValueError("Начало периода должно быть не позже конца.")
        if save_mssql and not settings.has_mssql():
            raise ConfigError(
                "MS SQL не настроен. Задайте MSSQL_* в .env или отключите сохранение в БД."
            )

        self.job_id = job_id or uuid.uuid4().hex
        self._settings = replace(settings, book_id=book_id)
        self.book_id = book_id
        self.period_start = period_start
        self.period_end = period_end
        self._save_mssql = save_mssql
        self._save_raw = save_raw
        self._wait_login_seconds = wait_login_seconds
        self._value_types = normalize_value_types(
            value_types
            if value_types is not None
            else (settings.value_type or DEFAULT_VALUE_TYPE,)
        )

        month_chunks = split_period_into_months(period_start, period_end)
        if not needs_monthly_chunks(period_start, period_end):
            month_chunks = [(period_start, period_end)]
        total_chunks = len(month_chunks) * len(self._value_types)

        self._lock = threading.Lock()
        self._progress = FetchProgress(
            status="idle",
            stage="Ожидание запуска",
            book_id=book_id,
            period_start=period_start,
            period_end=period_end,
            current_chunk=0,
            total_chunks=total_chunks,
            value_types=self._value_types,
        )
        self._code_queue: queue.Queue[str | None] = queue.Queue()
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None
        self._driver: WebDriver | None = None

    def snapshot(self) -> FetchProgress:
        with self._lock:
            p = self._progress
            return FetchProgress(
                status=p.status,
                stage=p.stage,
                book_id=p.book_id,
                period_start=p.period_start,
                period_end=p.period_end,
                current_chunk=p.current_chunk,
                total_chunks=p.total_chunks,
                hint=p.hint,
                error=p.error,
                result=p.result,
                value_type=p.value_type,
                value_types=p.value_types,
            )

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            raise RuntimeError("Загрузка уже запущена.")
        self._update(status="running", stage="Запуск…", error=None, result=None, hint=None)
        self._thread = threading.Thread(
            target=self._worker,
            name=f"fetch-job-{self.job_id[:8]}",
            daemon=True,
        )
        self._thread.start()

    def submit_code(self, code: str) -> None:
        text = (code or "").strip()
        if not text:
            raise ValueError("Введите код подтверждения.")
        self._code_queue.put(text)

    def cancel(self) -> None:
        self._cancel.set()
        try:
            self._code_queue.put_nowait(None)
        except queue.Full:
            pass
        self._update(status="cancelled", stage="Отмена…")

    def dismiss(self) -> None:
        """Убрать job из реестра после done/error/cancelled (поток уже завершён)."""
        with _jobs_lock:
            _JOBS.pop(self.job_id, None)

    def _update(self, **kwargs) -> None:
        with self._lock:
            for key, value in kwargs.items():
                setattr(self._progress, key, value)

    def _check_cancel(self) -> None:
        if self._cancel.is_set():
            raise RuntimeError("Загрузка отменена")

    def _code_provider(self, hint: str) -> str:
        self._check_cancel()
        self._update(
            status="awaiting_code",
            stage=f"Ожидание кода: {hint}",
            hint=hint,
        )
        code = self._code_queue.get()
        self._check_cancel()
        if code is None:
            raise RuntimeError("Загрузка отменена")
        self._update(
            status="running",
            stage="Проверка кода и продолжение входа…",
            hint=None,
        )
        return code

    def _worker(self) -> None:
        try:
            ensure_data_dirs()
            self._check_cancel()
            self._update(status="running", stage="Запуск браузера…", current_chunk=0)
            self._driver = create_driver(self._settings)
            self._check_cancel()

            self._update(stage="Авторизация (логин / пароль)…")
            auth = _auth_provider(
                self._settings,
                device_code_provider=self._code_provider,
                wait_login_seconds=self._wait_login_seconds,
            )

            month_chunks = split_period_into_months(self.period_start, self.period_end)
            if not needs_monthly_chunks(self.period_start, self.period_end):
                month_chunks = [(self.period_start, self.period_end)]
            total = len(month_chunks) * len(self._value_types)
            step = 0
            table = None

            for metric in self._value_types:
                self._check_cancel()
                settings = replace(self._settings, value_type=metric)
                for chunk_start, chunk_end in month_chunks:
                    self._check_cancel()
                    step += 1
                    self._update(
                        status="running",
                        stage=(
                            f"[{metric}] Загрузка {chunk_start} — {chunk_end} "
                            f"(шаг {step}/{total})…"
                        ),
                        current_chunk=step,
                        total_chunks=total,
                        value_type=metric,
                    )
                    table = _load_and_persist_period(
                        self._driver,
                        auth,
                        settings,
                        chunk_start,
                        chunk_end,
                        save_raw=self._save_raw,
                        save_mssql=self._save_mssql,
                    )
                    self._update(
                        stage=f"[{metric}] Сохранён шаг {step}/{total}",
                        current_chunk=step,
                    )

            if table is None:
                raise RuntimeError("Не удалось загрузить данные за период.")

            result = _result_from_table(
                table,
                book_id=self.book_id,
                period_start=self.period_start,
                period_end=self.period_end,
                save_mssql=self._save_mssql,
                save_raw=self._save_raw,
                value_types=self._value_types,
            )
            if self._cancel.is_set():
                self._update(status="cancelled", stage="Отменено", result=None)
            else:
                self._update(
                    status="done",
                    stage="Загрузка завершена",
                    result=result,
                    current_chunk=total,
                    hint=None,
                    error=None,
                )
        except Exception as exc:
            if self._cancel.is_set() or "отменен" in str(exc).lower():
                self._update(status="cancelled", stage="Отменено", error=None)
            else:
                self._update(
                    status="error",
                    stage="Ошибка загрузки",
                    error=format_exception_message(exc),
                )
        finally:
            driver = self._driver
            self._driver = None
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass


def register_session(session: FetchSession) -> FetchSession:
    _SESSIONS[session.session_id] = session
    return session


def get_session(session_id: str) -> FetchSession | None:
    return _SESSIONS.get(session_id)


def register_job(job: FetchJob) -> FetchJob:
    with _jobs_lock:
        _JOBS[job.job_id] = job
    return job


def get_job(job_id: str) -> FetchJob | None:
    with _jobs_lock:
        return _JOBS.get(job_id)


def list_active_jobs() -> list[FetchJob]:
    with _jobs_lock:
        jobs = list(_JOBS.values())
    return [job for job in jobs if job.snapshot().is_active]


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
    value_types: tuple[str, ...] | list[str] | None = None,
) -> FetchResult:
    """Однократная синхронная загрузка (совместимость)."""
    session = FetchSession(
        settings,
        book_id,
        period_start,
        period_end,
        save_mssql=save_mssql,
        save_raw=save_raw,
        wait_login_seconds=wait_login_seconds,
        value_types=value_types,
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
        return session.start()
    except DeviceCodeRequired:
        session.close()
        raise
