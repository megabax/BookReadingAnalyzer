"""Вкладка «Сравнение периодов»."""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from author_today.services.books import load_book_catalog
from author_today.ui.base import Page
from author_today.ui.cache import ReportCache
from author_today.ui.components.book_picker import BookPicker
from author_today.ui.presenters.compare import CompareChart, ComparePresenter
from config.settings import Settings


class ComparePage(Page):
    """Экран сравнения двух периодов."""

    def __init__(
        self,
        settings: Settings,
        book_picker: BookPicker,
        cache: ReportCache,
        presenter: ComparePresenter | None = None,
        chart: CompareChart | None = None,
    ) -> None:
        self._settings = settings
        self._book_picker = book_picker
        self._cache = cache
        self._presenter = presenter or ComparePresenter()
        self._chart = chart or CompareChart()

    @property
    def title(self) -> str:
        return "Сравнение периодов"

    def render(self) -> None:
        st.subheader("Сравнение двух периодов")
        st.caption(
            "По каждому дню: % главы от базовой. По периоду — среднее μ и σ по дням; "
            "p-value — Welch t-test (двусторонний)."
        )

        if not self._settings.has_mssql():
            st.warning("Настройте MS SQL в `.env` — отчёт строится из `chapter_reads`.")
            return

        catalog = load_book_catalog(self._settings)
        book_id = self._book_picker.pick(catalog, key_prefix="compare")

        default_b_start, default_b_end = self._default_period_b()
        st.markdown("**Период A**")
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            period_a_start = st.date_input(
                "A: начало",
                value=self._settings.default_period_start,
                key="compare_a_start",
            )
        with col_a2:
            period_a_end = st.date_input(
                "A: конец",
                value=self._settings.default_period_end,
                key="compare_a_end",
            )

        st.markdown("**Период B**")
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            period_b_start = st.date_input(
                "B: начало",
                value=default_b_start,
                key="compare_b_start",
            )
        with col_b2:
            period_b_end = st.date_input(
                "B: конец",
                value=default_b_end,
                key="compare_b_end",
            )

        with st.expander("Параметры сравнения", expanded=False):
            skip_book_page = st.checkbox(
                "Исключить «Страница книги»",
                value=True,
                key="compare_skip_book_page",
            )
            base_order = int(
                st.number_input(
                    "chapter_order базовой главы (100% для дневных долей)",
                    min_value=1,
                    value=2,
                    step=1,
                    key="compare_base_order",
                    help="Аналог --base-order в scripts/report_funnel_compare.py",
                )
            )

        build = st.button("Сравнить периоды", type="primary", key="compare_build")
        if st.button("Сбросить кэш сравнения", key="compare_clear_cache"):
            self._cache.clear_compare()
            st.toast("Кэш сравнения очищен")

        if not build:
            return

        if period_a_start > period_a_end:
            st.error("Период A: начало не может быть позже конца.")
            return
        if period_b_start > period_b_end:
            st.error("Период B: начало не может быть позже конца.")
            return

        try:
            with st.spinner("Загрузка данных из MS SQL…"):
                report = self._cache.funnel_compare(
                    book_id,
                    period_a_start,
                    period_a_end,
                    period_b_start,
                    period_b_end,
                    baseline_chapter_order=base_order,
                    skip_book_page=skip_book_page,
                )
        except ValueError as exc:
            st.error(str(exc))
            return
        except Exception as exc:
            st.error(f"Ошибка сравнения: {exc}")
            return

        if not report.rows:
            st.warning(
                "Нет данных для сравнения. "
                "Загрузите оба периода на вкладке «Загрузка»."
            )
            return

        sig_count = sum(
            1 for row in report.rows if row.p_value is not None and row.p_value < 0.05
        )
        st.success(
            f"book_id={book_id} · база: гл.{report.baseline_chapter_order} · "
            f"A: {report.period_a_start} — {report.period_a_end} · "
            f"B: {report.period_b_start} — {report.period_b_end}"
        )
        m1, m2, m3 = st.columns(3)
        m1.metric("Глав в сравнении", len(report.rows))
        m2.metric("Значимых (p<0.05)", sig_count)
        m3.metric("База chapter_order", report.baseline_chapter_order)

        st.markdown("**μ (% от базы) по главам: период A vs B**")
        self._chart.render(report)

        table_df = self._presenter.dataframe(report)
        st.dataframe(
            table_df.drop(columns=["p<0.05"]),
            hide_index=True,
            width="stretch",
            column_config={
                "μ A": st.column_config.NumberColumn(format="%.2f"),
                "σ A": st.column_config.NumberColumn(format="%.2f"),
                "μ B": st.column_config.NumberColumn(format="%.2f"),
                "σ B": st.column_config.NumberColumn(format="%.2f"),
                "Δμ B−A": st.column_config.NumberColumn(format="%.2f"),
                "p-value": st.column_config.NumberColumn(format="%.4f"),
            },
        )

        if sig_count:
            st.info(
                f"Статистически значимые главы (p<0.05): {sig_count}. "
                "См. таблицу и CSV."
            )

        st.download_button(
            "Скачать CSV",
            data=self._presenter.csv_bytes(report),
            file_name=self._presenter.csv_filename(report),
            mime="text/csv",
            key="compare_download_csv",
        )

        st.caption(
            "Для каждого дня: % = просмотры_главы / просмотры_базы × 100. "
            "σ — несмещённое s по дням. Дни с нулевой базой пропускаются."
        )

    def _default_period_b(self) -> tuple[date, date]:
        """Месяц перед дефолтным периодом A."""
        prev_start = self._settings.default_period_start
        period_b_end = prev_start - timedelta(days=1)
        period_b_start = period_b_end.replace(day=1)
        return period_b_start, period_b_end
