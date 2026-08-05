"""Панель «уже загружено в БД» для выбранной книги."""

from __future__ import annotations

import streamlit as st

from author_today.errors import AuthorTodayError
from author_today.services.books import load_book_data_info
from author_today.services.runs import delete_run, preview_delete_run
from author_today.storage.mssql_repo import LoadedRun
from author_today.ui.cache import ReportCache
from config.settings import Settings


class BookLoadInfoPanel:
    """Показывает покрытие chapter_reads / fetch_runs; удаление run (SRP)."""

    def __init__(
        self,
        settings: Settings,
        report_cache: ReportCache | None = None,
    ) -> None:
        self._settings = settings
        self._report_cache = report_cache

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
                        "метрика": run.value_type,
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
                "В отчётах суммируются run'ы выбранной метрики (сейчас по умолчанию hit), "
                "попадающие в даты read_date."
            )
            self._render_delete_run(book_id, info.runs)
        elif info.read_date_min:
            st.caption("Записи fetch_runs не найдены, но строки chapter_reads есть.")

    def _render_delete_run(self, book_id: int, runs: tuple[LoadedRun, ...]) -> None:
        with st.expander("Удалить загрузку (fetch_run)", expanded=False):
            st.caption(
                "Удаляются выбранный `fetch_runs` и все связанные строки "
                "`chapter_reads`. Операция необратима."
            )
            by_id = {run.run_id: run for run in runs}
            labels = {
                run.run_id: (
                    f"#{run.run_id} · {run.value_type} · "
                    f"{run.period_start} — {run.period_end} · "
                    f"{run.fetched_at.strftime('%Y-%m-%d %H:%M')}"
                )
                for run in runs
            }
            selected_id = st.selectbox(
                "Загрузка",
                options=list(labels.keys()),
                format_func=lambda rid: labels[rid],
                key=f"delete_run_select_{book_id}",
            )
            run = by_id[int(selected_id)]

            try:
                preview = preview_delete_run(self._settings, book_id, run.run_id)
            except AuthorTodayError as exc:
                st.error(str(exc))
                return

            st.warning(
                f"Будет удалено: **{preview.runs_count}** run "
                f"(id={', '.join(str(i) for i in preview.run_ids)}), "
                f"**{preview.reads_count}** строк chapter_reads."
            )
            confirm = st.checkbox(
                "Подтверждаю удаление",
                value=False,
                key=f"delete_run_confirm_{book_id}_{run.run_id}",
            )
            if st.button(
                "Удалить run",
                type="primary",
                disabled=not confirm,
                key=f"delete_run_btn_{book_id}",
            ):
                try:
                    result = delete_run(self._settings, book_id, run.run_id)
                except AuthorTodayError as exc:
                    st.error(str(exc))
                    return
                if self._report_cache is not None:
                    self._report_cache.clear_all()
                st.success(
                    f"Удалено: run_id={run.run_id}, "
                    f"chapter_reads={result.deleted_reads}."
                )
                st.rerun()
