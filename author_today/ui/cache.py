"""Кэш отчётов Streamlit — отделён от отрисовки страниц (SRP)."""

from __future__ import annotations

from datetime import date

import streamlit as st

from author_today.analyze.funnel import FunnelStep
from author_today.analyze.funnel_compare import FunnelCompareReport
from author_today.services.reports import load_funnel_compare, load_funnel_steps
from config.settings import Settings

# Settings нехешируем для st.cache_data — привязка через ReportCache.bind().
_settings: Settings | None = None


def mssql_cache_key(settings: Settings) -> str:
    if settings.mssql_server and settings.mssql_database:
        return f"{settings.mssql_server}|{settings.mssql_database}"
    return "mssql"


def _require_settings() -> Settings:
    if _settings is None:
        raise RuntimeError("ReportCache не инициализирован")
    return _settings


@st.cache_data(ttl=600, show_spinner=False)
def _cached_funnel_steps(
    _cache_key: str,
    book_id: int,
    period_start: date,
    period_end: date,
    skip_book_page: bool,
    baseline_chapter_order: int | None,
) -> list[FunnelStep]:
    return load_funnel_steps(
        _require_settings(),
        book_id,
        period_start,
        period_end,
        skip_book_page=skip_book_page,
        baseline_chapter_order=baseline_chapter_order,
    )


@st.cache_data(ttl=600, show_spinner=False)
def _cached_funnel_compare(
    _cache_key: str,
    book_id: int,
    period_a_start: date,
    period_a_end: date,
    period_b_start: date,
    period_b_end: date,
    baseline_chapter_order: int,
    skip_book_page: bool,
) -> FunnelCompareReport:
    return load_funnel_compare(
        _require_settings(),
        book_id,
        period_a_start,
        period_a_end,
        period_b_start,
        period_b_end,
        baseline_chapter_order=baseline_chapter_order,
        skip_book_page=skip_book_page,
    )


class ReportCache:
    """Фасад над st.cache_data: страницы зависят от этого класса, не от декораторов (DIP)."""

    def __init__(self, settings: Settings) -> None:
        global _settings
        _settings = settings
        self._settings = settings

    def funnel_steps(
        self,
        book_id: int,
        period_start: date,
        period_end: date,
        *,
        skip_book_page: bool,
        baseline_chapter_order: int | None,
    ) -> list[FunnelStep]:
        return _cached_funnel_steps(
            mssql_cache_key(self._settings),
            book_id,
            period_start,
            period_end,
            skip_book_page,
            baseline_chapter_order,
        )

    def funnel_compare(
        self,
        book_id: int,
        period_a_start: date,
        period_a_end: date,
        period_b_start: date,
        period_b_end: date,
        *,
        baseline_chapter_order: int,
        skip_book_page: bool,
    ) -> FunnelCompareReport:
        return _cached_funnel_compare(
            mssql_cache_key(self._settings),
            book_id,
            period_a_start,
            period_a_end,
            period_b_start,
            period_b_end,
            baseline_chapter_order,
            skip_book_page,
        )

    def clear_funnel(self) -> None:
        _cached_funnel_steps.clear()

    def clear_compare(self) -> None:
        _cached_funnel_compare.clear()

    def clear_all(self) -> None:
        self.clear_funnel()
        self.clear_compare()
