"""Загрузка статистики с author.today для UI."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date

from author_today.fetch.periods import needs_monthly_chunks, split_period_into_months
from author_today.domain.models import parse_dd_mm_columns
from author_today.pipeline.sync_reads import sync_reads_by_period
from config.settings import Settings


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
    raise RuntimeError(
        f"Требуется {hint}. Введите код в поле «Код подтверждения устройства» и повторите загрузку."
    )


def _device_code_provider(preset_code: str | None) -> Callable[[str], str]:
    code = (preset_code or "").strip()
    if code:
        return lambda _hint: code
    return lambda hint: _raise_device_code_required(hint)


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
    Загрузить таблицу прочтений за период и сохранить снимок.

    Открывает браузер (Selenium); при новом устройстве может понадобиться device_code.
    """
    if period_start > period_end:
        raise ValueError("Начало периода должно быть не позже конца.")

    if save_mssql and not settings.has_mssql():
        raise RuntimeError("MS SQL не настроен. Задайте MSSQL_* в .env или отключите сохранение в БД.")

    fetch_settings = replace(settings, book_id=book_id)

    table = sync_reads_by_period(
        fetch_settings,
        period_start,
        period_end,
        save_raw=save_raw,
        save_mssql=save_mssql,
        device_code_provider=_device_code_provider(device_code),
        wait_login_seconds=wait_login_seconds,
    )

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
