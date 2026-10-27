"""Вкладка «Продажи»."""

from __future__ import annotations

import streamlit as st

from author_today.errors import AuthorTodayError
from author_today.services.books import load_book_catalog
from author_today.services.sales import load_sales_period_report
from author_today.ui.base import Page
from author_today.ui.components.book_picker import BookPicker
from author_today.ui.presenters.sales import SalesChart, SalesPresenter
from config.settings import Settings


class SalesPage(Page):
    """Продажи книги за период: метрики, график по дням, таблица событий."""

    def __init__(
        self,
        settings: Settings,
        book_picker: BookPicker,
        presenter: SalesPresenter | None = None,
        chart: SalesChart | None = None,
    ) -> None:
        self._settings = settings
        self._book_picker = book_picker
        self._presenter = presenter or SalesPresenter()
        self._chart = chart or SalesChart()

    @property
    def title(self) -> str:
        return "Продажи"

    def render(self) -> None:
        st.subheader("Продажи")
        st.caption(
            "События из `sale_events` за выбранный период (по дате продажи). "
            "Загрузка — вкладка «Загрузка» → «Продажи»."
        )

        if not self._settings.has_mssql():
            st.warning("Настройте MS SQL в `.env`.")
            return

        catalog = load_book_catalog(self._settings)
        book_id = self._book_picker.pick(catalog, key_prefix="sales")

        col_start, col_end = st.columns(2)
        with col_start:
            period_start = st.date_input(
                "Начало периода",
                value=self._settings.default_period_start,
                key="sales_period_start",
            )
        with col_end:
            period_end = st.date_input(
                "Конец периода",
                value=self._settings.default_period_end,
                key="sales_period_end",
            )

        if period_start > period_end:
            st.error("Начало периода не может быть позже конца.")
            return

        try:
            report = load_sales_period_report(
                self._settings, book_id, period_start, period_end
            )
        except AuthorTodayError as exc:
            st.error(str(exc))
            return
        except ValueError as exc:
            st.error(str(exc))
            return

        self._presenter.metrics(report)
        st.markdown("#### По дням")
        self._chart.render(report)
        st.markdown("#### События")
        self._presenter.events_table(report)
        if report.sales_count:
            st.caption(
                "При нескольких `sale_runs` за одни и те же дни строки суммируются — "
                "дубли загрузок завышают цифры."
            )
