"""Вкладка «Воронка»."""

from __future__ import annotations

import streamlit as st

from author_today.analyze.formatting import pct_column_label
from author_today.analyze.funnel import find_funnel_drop_points
from author_today.errors import AuthorTodayError
from author_today.services.books import load_book_catalog
from author_today.ui.base import Page
from author_today.ui.cache import ReportCache
from author_today.ui.components.book_picker import BookPicker
from author_today.ui.presenters.funnel import (
    FunnelChart,
    FunnelPresenter,
    render_drop_summary,
)
from config.settings import Settings


class FunnelPage(Page):
    """Экран воронки дочитываний; зависит от абстракций BookPicker / ReportCache (DIP)."""

    def __init__(
        self,
        settings: Settings,
        book_picker: BookPicker,
        cache: ReportCache,
        presenter: FunnelPresenter | None = None,
        chart: FunnelChart | None = None,
    ) -> None:
        self._settings = settings
        self._book_picker = book_picker
        self._cache = cache
        self._presenter = presenter or FunnelPresenter()
        self._chart = chart or FunnelChart()

    @property
    def title(self) -> str:
        return "Воронка"

    def render(self) -> None:
        st.subheader("Воронка дочитываний")
        st.caption(
            "Сумма просмотров по главам за период из MS SQL; "
            "% от базовой главы и % от предыдущей."
        )

        if not self._settings.has_mssql():
            st.warning("Настройте MS SQL в `.env` — отчёт строится из `chapter_reads`.")
            return

        catalog = load_book_catalog(self._settings)
        book_id = self._book_picker.pick(catalog, key_prefix="funnel")

        col_start, col_end = st.columns(2)
        with col_start:
            period_start = st.date_input(
                "Начало периода",
                value=self._settings.default_period_start,
                key="funnel_period_start",
            )
        with col_end:
            period_end = st.date_input(
                "Конец периода",
                value=self._settings.default_period_end,
                key="funnel_period_end",
            )

        with st.expander("Параметры воронки", expanded=False):
            skip_book_page = st.checkbox(
                "Исключить «Страница книги»",
                value=True,
                key="funnel_skip_book_page",
                help="Как флаг --skip-book-page в CLI.",
            )
            use_custom_base = st.checkbox(
                "База 100% — не первая глава воронки",
                value=False,
                key="funnel_use_custom_base",
            )
            baseline_chapter_order: int | None = None
            if use_custom_base:
                baseline_chapter_order = int(
                    st.number_input(
                        "chapter_order базовой главы (как на сайте)",
                        min_value=1,
                        value=2,
                        step=1,
                        key="funnel_base_order",
                        help="Аналог --base-order в scripts/report_funnel.py",
                    )
                )

        build = st.button("Построить воронку", type="primary", key="funnel_build")
        if st.button("Сбросить кэш отчёта", key="funnel_clear_cache"):
            self._cache.clear_all()
            st.toast("Кэш отчётов очищен")

        if not build:
            return

        if period_start > period_end:
            st.error("Начало периода не может быть позже конца.")
            return

        try:
            with st.spinner("Загрузка данных из MS SQL…"):
                steps = self._cache.funnel_steps(
                    book_id,
                    period_start,
                    period_end,
                    skip_book_page=skip_book_page,
                    baseline_chapter_order=baseline_chapter_order,
                )
        except AuthorTodayError as exc:
            st.error(str(exc))
            return
        except Exception as exc:
            st.error(f"Ошибка построения воронки: {exc}")
            return

        if not steps:
            st.warning(
                "Нет данных за выбранный период. "
                "Загрузите статистику на вкладке «Загрузка»."
            )
            return

        pct_col = pct_column_label(baseline_chapter_order)
        baseline_step = (
            next(
                (s for s in steps if s.site_chapter_order == baseline_chapter_order),
                None,
            )
            if baseline_chapter_order is not None
            else steps[0]
        )
        drops = find_funnel_drop_points(steps, top_n=3)
        drop_nums = drops.highlighted_step_nums

        st.success(
            f"book_id={book_id}, {period_start} — {period_end} · шагов: {len(steps)}"
        )
        m1, m2, m3 = st.columns(3)
        m1.metric("Шагов воронки", len(steps))
        if baseline_step:
            m2.metric(
                "База (просмотры)",
                baseline_step.total_views,
                help=baseline_step.chapter_name,
            )
        m3.metric(
            "Последняя глава, % от базы",
            f"{steps[-1].pct_of_first:.1f}%",
        )

        render_drop_summary(drops)

        st.markdown(f"**{pct_col}** по шагам воронки")
        self._chart.render(steps, y_title=pct_col, drop_step_nums=drop_nums)

        table_df = self._presenter.dataframe(
            steps,
            baseline_chapter_order=baseline_chapter_order,
            drop_step_nums=drop_nums,
        )
        if drop_nums:
            st.dataframe(
                self._presenter.style_drop_rows(table_df, drop_nums),
                width="stretch",
            )
        else:
            st.dataframe(
                table_df,
                hide_index=True,
                width="stretch",
                column_config={
                    "% от пред.": st.column_config.NumberColumn(format="%.1f"),
                    pct_col: st.column_config.NumberColumn(format="%.1f"),
                },
            )

        st.download_button(
            "Скачать CSV",
            data=self._presenter.csv_bytes(
                steps,
                baseline_chapter_order=baseline_chapter_order,
            ),
            file_name=self._presenter.csv_filename(book_id, period_start, period_end),
            mime="text/csv",
            key="funnel_download_csv",
        )

        st.caption(
            "Красные треугольники и подсветка строк — топ провалов "
            "(падение % от предыдущей главы и/или % от базы к предыдущему шагу). "
            "Повторные загрузки того же периода суммируются в БД."
        )
