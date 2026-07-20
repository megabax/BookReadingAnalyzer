"""Панель «уже загружено в БД» для выбранной книги."""

from __future__ import annotations

import streamlit as st

from author_today.services.books import load_book_data_info
from config.settings import Settings


class BookLoadInfoPanel:
    """Показывает покрытие chapter_reads / fetch_runs (SRP)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def render(self, book_id: int) -> None:
        if not self._settings.has_mssql():
            return

        info = load_book_data_info(self._settings, book_id)
        if info is None:
            return

        st.markdown("**Уже загружено в БД**")
        if not info.runs and info.read_date_min is None:
            st.info(f"По book_id={book_id} в MS SQL пока нет снимков.")
            return

        if info.read_date_min and info.read_date_max:
            st.caption(
                f"Покрытие по дням прочтений (chapter_reads): "
                f"**{info.read_date_min}** — **{info.read_date_max}**"
            )

        if info.runs:
            st.dataframe(
                [
                    {
                        "run_id": run.run_id,
                        "период с": run.period_start,
                        "период по": run.period_end,
                        "загружено": run.fetched_at.strftime("%Y-%m-%d %H:%M"),
                    }
                    for run in info.runs
                ],
                hide_index=True,
                width="stretch",
            )
            st.caption(
                "В отчётах за произвольный период суммируются все run'ы, "
                "попадающие в выбранные даты read_date."
            )
        elif info.read_date_min:
            st.caption("Записи fetch_runs не найдены, но строки chapter_reads есть.")
