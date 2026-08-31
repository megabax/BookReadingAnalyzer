"""Форматирование воронки для таблицы, CSV и Altair."""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from author_today.analyze.formatting import pct_column_label
from author_today.analyze.funnel import (
    FunnelDropReport,
    FunnelStep,
    default_funnel_csv_path,
    find_funnel_drop_points,
    save_funnel_csv,
)


class FunnelPresenter:
    """Преобразование FunnelStep → DataFrame / CSV (SRP: без виджетов ввода)."""

    def dataframe(
        self,
        steps: list[FunnelStep],
        *,
        baseline_chapter_order: int | None,
        drop_step_nums: frozenset[int] | None = None,
    ) -> pd.DataFrame:
        pct_col = pct_column_label(baseline_chapter_order)
        highlighted = drop_step_nums or frozenset()
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
                    "Провал": "⚠" if step.step_num in highlighted else "",
                }
                for step in steps
            ]
        )

    def style_drop_rows(
        self,
        df: pd.DataFrame,
        drop_step_nums: frozenset[int],
    ):
        """Подсветка строк-провалов для st.dataframe."""

        def _row_style(row: pd.Series) -> list[str]:
            if int(row["№"]) in drop_step_nums:
                return ["background-color: #ffe5e5"] * len(row)
            return [""] * len(row)

        return df.style.apply(_row_style, axis=1)

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
    """Отрисовка графика воронки; провалы — красные точки."""

    def render(
        self,
        steps: list[FunnelStep],
        *,
        y_title: str,
        drop_step_nums: frozenset[int] | None = None,
    ) -> None:
        highlighted = drop_step_nums or frozenset()
        chart_df = pd.DataFrame(
            {
                "step": [s.step_num for s in steps],
                "pct": [float(s.pct_of_first) for s in steps],
                "chapter": [s.chapter_name for s in steps],
                "is_drop": [s.step_num in highlighted for s in steps],
            }
        )
        line = (
            alt.Chart(chart_df)
            .mark_line(color="#1f77b4")
            .encode(
                x=alt.X("step:Q", title="№ шага воронки"),
                y=alt.Y("pct:Q", title=y_title, scale=alt.Scale(zero=False)),
            )
        )
        normal_pts = (
            alt.Chart(chart_df[~chart_df["is_drop"]])
            .mark_point(size=60, color="#1f77b4", filled=True)
            .encode(
                x="step:Q",
                y="pct:Q",
                tooltip=[
                    alt.Tooltip("step:Q", title="№"),
                    alt.Tooltip("chapter:N", title="Глава"),
                    alt.Tooltip("pct:Q", title=y_title, format=".1f"),
                ],
            )
        )
        drop_pts = (
            alt.Chart(chart_df[chart_df["is_drop"]])
            .mark_point(size=120, color="#d62728", filled=True, shape="triangle-down")
            .encode(
                x="step:Q",
                y="pct:Q",
                tooltip=[
                    alt.Tooltip("step:Q", title="№"),
                    alt.Tooltip("chapter:N", title="Глава"),
                    alt.Tooltip("pct:Q", title=y_title, format=".1f"),
                ],
            )
        )
        chart = alt.layer(line, normal_pts, drop_pts).properties(height=420)
        st.altair_chart(chart, use_container_width=True)


def render_drop_summary(report: FunnelDropReport) -> None:
    """Краткий блок «точки провала» над графиком."""
    if not report.from_previous and not report.from_baseline:
        st.info("Явных провалов не найдено (нет падений между шагами).")
        return

    st.markdown("**Точки провала** (топ по падению)")
    col_a, col_b = st.columns(2)
    with col_a:
        st.caption("Vs предыдущая глава")
        if report.from_previous:
            for point in report.from_previous:
                st.markdown(f"- {point.label}")
        else:
            st.caption("—")
    with col_b:
        st.caption("Падение % от базы к предыдущему шагу")
        if report.from_baseline:
            for point in report.from_baseline:
                st.markdown(f"- {point.label}")
        else:
            st.caption("—")
