"""Вкладка «Тренд дочитывания»."""

from __future__ import annotations

from datetime import date

import streamlit as st

from author_today.analyze.formatting import pct_column_label
from author_today.errors import AuthorTodayError
from author_today.services.books import load_book_catalog
from author_today.ui.base import Page
from author_today.ui.cache import ReportCache
from author_today.ui.components.book_picker import BookPicker
from author_today.ui.presenters.trend import TrendChart, TrendPresenter
from config.settings import Settings


class TrendPage(Page):
    """% выбранной главы от базы по месяцам; глава по умолчанию — последняя."""

    def __init__(
        self,
        settings: Settings,
        book_picker: BookPicker,
        cache: ReportCache,
        presenter: TrendPresenter | None = None,
        chart: TrendChart | None = None,
    ) -> None:
        self._settings = settings
        self._book_picker = book_picker
        self._cache = cache
        self._presenter = presenter or TrendPresenter()
        self._chart = chart or TrendChart()

    @property
    def title(self) -> str:
        return "Тренд дочитывания"

    def render(self) -> None:
        st.subheader("Тренд дочитывания")
        st.caption(
            "По каждому календарному месяцу: сумма просмотров выбранной главы "
            "в % от базовой (та же метрика, что у воронки). "
            "По умолчанию — последняя глава после фильтра обложки."
        )

        if not self._settings.has_mssql():
            st.warning("Настройте MS SQL в `.env` — отчёт строится из `chapter_reads`.")
            return

        catalog = load_book_catalog(self._settings)
        book_id = self._book_picker.pick(catalog, key_prefix="trend")

        col_start, col_end = st.columns(2)
        with col_start:
            period_start = st.date_input(
                "Начало периода",
                value=self._settings.default_period_start,
                key="trend_period_start",
            )
        with col_end:
            period_end = st.date_input(
                "Конец периода",
                value=self._settings.default_period_end,
                key="trend_period_end",
            )

        with st.expander("Параметры тренда", expanded=True):
            skip_book_page = st.checkbox(
                "Исключить «Страница книги»",
                value=True,
                key="trend_skip_book_page",
                help="Как воронка и сравнение периодов: обложка не участвует в выборе глав.",
            )
            use_custom_base = st.checkbox(
                "База 100% — не первая глава воронки",
                value=False,
                key="trend_use_custom_base",
            )
            baseline_chapter_order: int | None = None
            if use_custom_base:
                baseline_chapter_order = int(
                    st.number_input(
                        "chapter_order базовой главы (как на сайте)",
                        min_value=1,
                        value=2,
                        step=1,
                        key="trend_base_order",
                    )
                )

            target_chapter_order = self._pick_target_chapter(
                book_id,
                period_start,
                period_end,
                skip_book_page=skip_book_page,
            )

        build = st.button("Построить тренд", type="primary", key="trend_build")
        if st.button("Сбросить кэш отчёта", key="trend_clear_cache"):
            self._cache.clear_all()
            st.toast("Кэш отчётов очищен")

        if not build:
            return

        if period_start > period_end:
            st.error("Начало периода не может быть позже конца.")
            return
        if target_chapter_order is None:
            st.error("Выберите главу для тренда (нужны данные за период в БД).")
            return

        try:
            with st.spinner("Загрузка данных из MS SQL…"):
                report = self._cache.completion_trend(
                    book_id,
                    period_start,
                    period_end,
                    target_chapter_order=target_chapter_order,
                    skip_book_page=skip_book_page,
                    baseline_chapter_order=baseline_chapter_order,
                )
        except AuthorTodayError as exc:
            st.error(str(exc))
            return
        except Exception as exc:
            st.error(f"Ошибка построения тренда: {exc}")
            return

        pct_col = pct_column_label(baseline_chapter_order)
        st.success(
            f"book_id={book_id}, {period_start} — {period_end} · "
            f"глава {report.target_chapter_order} «{report.target_chapter_name}» · "
            f"месяцев: {len(report.points)}"
        )
        m1, m2, m3 = st.columns(3)
        m1.metric("Месяцев", len(report.points))
        m2.metric(
            "Первый месяц",
            f"{report.points[0].pct_of_baseline:.1f}%",
            help=report.points[0].month_label,
        )
        m3.metric(
            "Последний месяц",
            f"{report.points[-1].pct_of_baseline:.1f}%",
            help=report.points[-1].month_label,
        )

        st.markdown(f"**{pct_col}** по месяцам")
        self._chart.render(report, y_title=pct_col)

        table_df = self._presenter.dataframe(report)
        st.dataframe(
            table_df,
            hide_index=True,
            width="stretch",
            column_config={
                pct_col: st.column_config.NumberColumn(format="%.1f"),
            },
        )

        st.download_button(
            "Скачать CSV",
            data=self._presenter.csv_bytes(report),
            file_name=self._presenter.csv_filename(report),
            mime="text/csv",
            key="trend_download_csv",
        )

        st.caption(
            "Метрика — сумма просмотров за месяц (как воронка), не среднее дневных %. "
            "Повторные загрузки того же периода суммируются в БД."
        )

    def _pick_target_chapter(
        self,
        book_id: int,
        period_start: date,
        period_end: date,
        *,
        skip_book_page: bool,
    ) -> int | None:
        if period_start > period_end:
            st.caption("Исправьте период, чтобы загрузить список глав.")
            return None

        try:
            options = self._cache.chapter_options(
                book_id,
                period_start,
                period_end,
                skip_book_page=skip_book_page,
            )
        except AuthorTodayError as exc:
            st.warning(str(exc))
            return None
        except Exception as exc:
            st.warning(f"Не удалось загрузить список глав: {exc}")
            return None

        if not options:
            st.caption(
                "Нет глав за период в БД. Загрузите статистику на вкладке «Загрузка»."
            )
            return None

        labels = [f"{order} — {name}" for order, name in options]
        default_index = len(labels) - 1
        # Ключ сбрасывается при смене книги/периода/фильтра — снова выбирается последняя глава.
        widget_key = (
            f"trend_target_chapter_{book_id}_{period_start}_{period_end}_{skip_book_page}"
        )
        choice = st.selectbox(
            "Глава (по умолчанию последняя)",
            options=labels,
            index=default_index,
            key=widget_key,
            help="Порядок chapter_order как на сайте / в воронке.",
        )
        selected_label_index = labels.index(choice)
        return options[selected_label_index][0]
