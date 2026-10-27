"""Панель загруженных sale_runs на вкладке «Загрузка»."""

from __future__ import annotations

import streamlit as st

from author_today.errors import AuthorTodayError
from author_today.services.sales import (
    list_sale_events_for_run,
    load_sale_load_info,
    work_format_label,
)
from config.settings import Settings


class SaleLoadInfoPanel:
    """Список sale_runs и просмотр событий выбранного run."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def render(self, book_id: int) -> None:
        if not self._settings.has_mssql():
            return

        with st.expander("Загруженные продажи (sale_runs)", expanded=False):
            try:
                info = load_sale_load_info(self._settings, book_id)
            except AuthorTodayError as exc:
                st.error(str(exc))
                return

            if info is None:
                return

            if not info.runs and info.sale_date_min is None:
                st.info(f"По book_id={book_id} продаж в MS SQL пока нет.")
                return

            if info.sale_date_min and info.sale_date_max:
                st.caption(
                    f"Даты продаж (sale_events): "
                    f"**{info.sale_date_min}** — **{info.sale_date_max}**"
                )

            if info.runs:
                st.dataframe(
                    [
                        {
                            "run_id": run.run_id,
                            "период с": run.period_start,
                            "период по": run.period_end,
                            "событий": run.events_count,
                            "загружено": run.fetched_at.strftime("%Y-%m-%d %H:%M"),
                        }
                        for run in info.runs
                    ],
                    hide_index=True,
                    width="stretch",
                )
                st.caption(
                    "Повторная загрузка того же периода добавит новый run; "
                    "на вкладке «Продажи» события за пересекающиеся дни суммируются."
                )
                self._render_run_preview(book_id, info.runs)
            elif info.sale_date_min:
                st.caption("Есть sale_events, но список sale_runs пуст.")

    def _render_run_preview(self, book_id: int, runs) -> None:
        labels = {
            run.run_id: (
                f"#{run.run_id} · {run.period_start} — {run.period_end} · "
                f"{run.events_count} шт. · "
                f"{run.fetched_at.strftime('%Y-%m-%d %H:%M')}"
            )
            for run in runs
        }
        selected_id = st.selectbox(
            "Показать события run",
            options=list(labels.keys()),
            format_func=lambda rid: labels[rid],
            key=f"sale_run_preview_{book_id}",
        )
        try:
            events = list_sale_events_for_run(
                self._settings, book_id, int(selected_id)
            )
        except AuthorTodayError as exc:
            st.error(str(exc))
            return

        if not events:
            st.info("В этом run нет событий.")
            return

        st.dataframe(
            [
                {
                    "время": e.processed_at.strftime("%Y-%m-%d %H:%M"),
                    "формат": work_format_label(e.work_format),
                    "цена": e.price,
                    "комиссия": e.commission,
                    "доход": e.author_income,
                }
                for e in events
            ],
            hide_index=True,
            width="stretch",
        )
