"""Форматирование тренда дочитывания для таблицы, CSV и Altair."""

from __future__ import annotations

import tempfile
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from author_today.analyze.completion_trend import (
    CompletionTrendReport,
    default_completion_trend_csv_path,
    save_completion_trend_csv,
)
from author_today.analyze.formatting import pct_column_label


class TrendPresenter:
    """CompletionTrendReport → DataFrame / CSV (SRP: без виджетов ввода)."""

    def dataframe(self, report: CompletionTrendReport) -> pd.DataFrame:
        pct_col = pct_column_label(report.baseline_chapter_order)
        return pd.DataFrame(
            [
                {
                    "Месяц": point.month_label,
                    "Начало": point.month_start,
                    "Конец": point.month_end,
                    "Просмотры": point.target_views,
                    "База": point.baseline_views,
                    pct_col: point.pct_of_baseline,
                }
                for point in report.points
            ]
        )

    def csv_bytes(self, report: CompletionTrendReport) -> bytes:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "completion_trend.csv"
            save_completion_trend_csv(report, path)
            return path.read_bytes()

    def csv_filename(self, report: CompletionTrendReport) -> str:
        return default_completion_trend_csv_path(
            report.book_id,
            report.period_start,
            report.period_end,
        ).name


class TrendChart:
    """Два ряда на одном графике: % от базы (слева) и просмотры главы (справа)."""

    def render(self, report: CompletionTrendReport, *, y_title: str) -> None:
        chart_df = pd.DataFrame(
            {
                "month": [p.month_label for p in report.points],
                "pct": [float(p.pct_of_baseline) for p in report.points],
                "views": [float(p.target_views) for p in report.points],
                "baseline": [float(p.baseline_views) for p in report.points],
            }
        )
        views_title = f"Просмотры «{report.target_chapter_name}»"
        base = alt.Chart(chart_df).encode(
            x=alt.X("month:N", title="Месяц", sort=None),
            tooltip=[
                alt.Tooltip("month:N", title="Месяц"),
                alt.Tooltip("pct:Q", title=y_title, format=".1f"),
                alt.Tooltip("views:Q", title=views_title, format=",.0f"),
                alt.Tooltip("baseline:Q", title="База", format=",.0f"),
            ],
        )
        pct_line = base.mark_line(point=True, color="#1f77b4").encode(
            y=alt.Y(
                "pct:Q",
                title=y_title,
                scale=alt.Scale(zero=False),
                axis=alt.Axis(titleColor="#1f77b4"),
            ),
        )
        views_line = base.mark_line(point=True, color="#ff7f0e").encode(
            y=alt.Y(
                "views:Q",
                title=views_title,
                scale=alt.Scale(zero=True),
                axis=alt.Axis(titleColor="#ff7f0e", orient="right"),
            ),
        )
        chart = (
            alt.layer(pct_line, views_line)
            .resolve_scale(y="independent")
            .properties(height=420)
        )
        st.altair_chart(chart, use_container_width=True)
