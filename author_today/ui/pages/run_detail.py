"""Экран просмотра одного fetch_run (chapter_reads)."""

from __future__ import annotations

import streamlit as st

from author_today.errors import AuthorTodayError
from author_today.services.runs import load_fetch_run_detail
from author_today.ui.presenters.run_detail import RunDetailPresenter
from config.settings import Settings


class RunDetailPage:
    """Полный снимок загрузки: главы сверху вниз в порядке chapter_order."""

    def __init__(
        self,
        settings: Settings,
        *,
        book_id: int,
        run_id: int,
        presenter: RunDetailPresenter | None = None,
    ) -> None:
        self._settings = settings
        self._book_id = book_id
        self._run_id = run_id
        self._presenter = presenter or RunDetailPresenter()

    def render(self) -> None:
        if st.button("← К списку загрузок", key="run_detail_back"):
            for key in ("view", "book_id", "run_id"):
                if key in st.query_params:
                    del st.query_params[key]
            st.rerun()

        st.subheader(f"Загрузка run_id={self._run_id}")

        try:
            detail = load_fetch_run_detail(
                self._settings, self._book_id, self._run_id
            )
        except AuthorTodayError as exc:
            st.error(str(exc))
            return

        st.caption(
            f"book_id={detail.book_id} · метрика **{detail.value_type}** · "
            f"период {detail.period_start} — {detail.period_end} · "
            f"загружено {detail.fetched_at.strftime('%Y-%m-%d %H:%M')} · "
            f"строк chapter_reads: {len(detail.rows)}"
        )

        if not detail.rows:
            st.info("У этого run нет строк chapter_reads.")
            return

        wide = self._presenter.wide_dataframe(detail)
        st.dataframe(wide, hide_index=True, width="stretch")
        st.caption(
            "Строки — главы в порядке `chapter_order` (как на сайте). "
            "Столбцы — дни `read_date`."
        )
