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
from author_today.storage.mssql_repo import BookNote


def notes_in_report_months(
    notes: list[BookNote],
    report: CompletionTrendReport,
) -> pd.DataFrame:
    """
    Заметки, попадающие в период отчёта и в месяцы точек тренда.

    Несколько заметок в одном месяце склеиваются для подписи на графике.
    """
    month_set = {p.month_label for p in report.points}
    rows: list[dict] = []
    for note in notes:
        if note.note_date < report.period_start or note.note_date > report.period_end:
            continue
        month = f"{note.note_date:%Y-%m}"
        if month not in month_set:
            continue
        rows.append(
            {
                "month": month,
                "note_date": note.note_date.isoformat(),
                "body": note.body,
            }
        )
    if not rows:
        return pd.DataFrame(columns=["month", "label", "short"])

    df = pd.DataFrame(rows)
    labels: list[dict] = []
    for month, group in df.groupby("month", sort=False):
        parts = [f"{row.note_date}: {row.body}" for row in group.itertuples()]
        labels.append(
            {
                "month": month,
                "label": " | ".join(parts),
                "short": parts[0] if len(parts) == 1 else f"{len(parts)} заметки",
            }
        )
    return pd.DataFrame(labels)


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

    def render(
        self,
        report: CompletionTrendReport,
        *,
        y_title: str,
        notes: list[BookNote] | None = None,
    ) -> None:
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
        layers: list[alt.Chart] = [pct_line, views_line]

        notes_df = notes_in_report_months(notes or [], report)
        if not notes_df.empty:
            note_rules = (
                alt.Chart(notes_df)
                .mark_rule(color="#d62728", strokeDash=[6, 4], strokeWidth=2)
                .encode(
                    x=alt.X("month:N", sort=None),
                    tooltip=[
                        alt.Tooltip("month:N", title="Месяц"),
                        alt.Tooltip("label:N", title="Заметки"),
                    ],
                )
            )
            note_points = (
                alt.Chart(notes_df)
                .mark_point(shape="diamond", size=80, color="#d62728", filled=True)
                .encode(
                    x=alt.X("month:N", sort=None),
                    y=alt.value(20),
                    tooltip=[
                        alt.Tooltip("month:N", title="Месяц"),
                        alt.Tooltip("label:N", title="Заметки"),
                    ],
                )
            )
            layers.extend([note_rules, note_points])

        chart = (
            alt.layer(*layers)
            .resolve_scale(y="independent")
            .properties(height=420)
        )
        st.altair_chart(chart, use_container_width=True)
