"""Форматирование сравнения периодов для таблицы, CSV и Altair."""

from __future__ import annotations

import tempfile
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from author_today.analyze.funnel_compare import FunnelCompareReport, save_funnel_compare_csv


class ComparePresenter:
    """FunnelCompareReport → DataFrame / CSV (SRP)."""

    def dataframe(self, report: FunnelCompareReport) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "chapter_order": row.site_chapter_order,
                    "Глава": row.chapter_name,
                    "μ A": row.period_a.mean_pct,
                    "σ A": row.period_a.sigma_pct,
                    "n A": row.period_a.n_days,
                    "μ B": row.period_b.mean_pct,
                    "σ B": row.period_b.sigma_pct,
                    "n B": row.period_b.n_days,
                    "Δμ B−A": row.mean_diff,
                    "p-value": row.p_value,
                    "p<0.05": row.p_value is not None and row.p_value < 0.05,
                }
                for row in report.rows
            ]
        )

    def csv_bytes(self, report: FunnelCompareReport) -> bytes:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "funnel_compare.csv"
            save_funnel_compare_csv(report, path)
            return path.read_bytes()

    def csv_filename(self, report: FunnelCompareReport) -> str:
        return (
            f"funnel_compare_{report.book_id}_"
            f"{report.period_a_start:%Y%m%d}_{report.period_a_end:%Y%m%d}_vs_"
            f"{report.period_b_start:%Y%m%d}_{report.period_b_end:%Y%m%d}.csv"
        )


class CompareChart:
    """Отрисовка графика сравнения μ A vs B."""

    def render(self, report: FunnelCompareReport) -> None:
        rows: list[dict] = []
        for row in report.rows:
            rows.append(
                {
                    "order": row.site_chapter_order,
                    "chapter": row.chapter_name,
                    "period": "A",
                    "mean_pct": float(row.period_a.mean_pct),
                }
            )
            rows.append(
                {
                    "order": row.site_chapter_order,
                    "chapter": row.chapter_name,
                    "period": "B",
                    "mean_pct": float(row.period_b.mean_pct),
                }
            )
        chart_df = pd.DataFrame(rows)
        chart = (
            alt.Chart(chart_df)
            .mark_line(point=True)
            .encode(
                x=alt.X("order:Q", title="chapter_order"),
                y=alt.Y("mean_pct:Q", title="μ, % от базы", scale=alt.Scale(zero=False)),
                color=alt.Color("period:N", title="Период"),
                tooltip=[
                    alt.Tooltip("order:Q", title="chapter_order"),
                    alt.Tooltip("chapter:N", title="Глава"),
                    alt.Tooltip("period:N", title="Период"),
                    alt.Tooltip("mean_pct:Q", title="μ, %", format=".2f"),
                ],
            )
            .properties(height=420)
        )
        st.altair_chart(chart, use_container_width=True)
