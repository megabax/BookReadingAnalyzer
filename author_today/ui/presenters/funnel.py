"""Форматирование воронки для таблицы, CSV и Altair."""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from author_today.analyze.formatting import pct_column_label
from author_today.analyze.funnel import FunnelStep, default_funnel_csv_path, save_funnel_csv


class FunnelPresenter:
    """Преобразование FunnelStep → DataFrame / CSV (SRP: без виджетов ввода)."""

    def dataframe(
        self,
        steps: list[FunnelStep],
        *,
        baseline_chapter_order: int | None,
    ) -> pd.DataFrame:
        pct_col = pct_column_label(baseline_chapter_order)
        return pd.DataFrame(
            [
                {
                    "№": step.step_num,
                    "chapter_order": step.site_chapter_order,
                    "Глава": step.chapter_name,
                    "Просмотры": step.total_views,
                    pct_col: step.pct_of_first,
                    "% от пред.": step.pct_of_previous,
                    "Падение": step.drop_from_previous,
                }
                for step in steps
            ]
        )

    def csv_bytes(
        self,
        steps: list[FunnelStep],
        *,
        baseline_chapter_order: int | None,
    ) -> bytes:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "funnel.csv"
            save_funnel_csv(steps, path, baseline_chapter_order=baseline_chapter_order)
            return path.read_bytes()

    def csv_filename(
        self,
        book_id: int,
        period_start: date,
        period_end: date,
    ) -> str:
        return default_funnel_csv_path(book_id, period_start, period_end).name


class FunnelChart:
    """Отрисовка графика воронки (SRP: только визуализация)."""

    def render(self, steps: list[FunnelStep], *, y_title: str) -> None:
        chart_df = pd.DataFrame(
            {
                "step": [s.step_num for s in steps],
                "pct": [float(s.pct_of_first) for s in steps],
                "chapter": [s.chapter_name for s in steps],
            }
        )
        chart = (
            alt.Chart(chart_df)
            .mark_line(point=True)
            .encode(
                x=alt.X("step:Q", title="№ шага воронки"),
                y=alt.Y("pct:Q", title=y_title, scale=alt.Scale(zero=False)),
                tooltip=[
                    alt.Tooltip("step:Q", title="№"),
                    alt.Tooltip("chapter:N", title="Глава"),
                    alt.Tooltip("pct:Q", title=y_title, format=".1f"),
                ],
            )
            .properties(height=420)
        )
        st.altair_chart(chart, use_container_width=True)
