"""Презентация отчёта по продажам."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from author_today.services.sales import work_format_label
from author_today.storage.mssql_repo import SalesPeriodReport


class SalesPresenter:
    def metrics(self, report: SalesPeriodReport) -> None:
        c1, c2, c3 = st.columns(3)
        c1.metric("Продаж", report.sales_count)
        c2.metric("Доход автора, ₽", f"{report.income_sum:,.2f}".replace(",", " "))
        c3.metric("Сумма цен, ₽", f"{report.price_sum:,.2f}".replace(",", " "))

    def events_table(self, report: SalesPeriodReport) -> None:
        if not report.events:
            st.info("За период продаж нет.")
            return
        st.dataframe(
            [
                {
                    "время": e.processed_at.strftime("%Y-%m-%d %H:%M"),
                    "формат": work_format_label(e.work_format),
                    "цена": e.price,
                    "комиссия": e.commission,
                    "доход": e.author_income,
                    "run_id": e.run_id,
                }
                for e in report.events
            ],
            hide_index=True,
            width="stretch",
        )


class SalesChart:
    def render(self, report: SalesPeriodReport) -> None:
        if not report.daily:
            st.caption("Нет дневных точек для графика.")
            return

        frame = pd.DataFrame(
            [
                {
                    "day": p.day.isoformat(),
                    "sales_count": p.sales_count,
                    "income_sum": p.income_sum,
                }
                for p in report.daily
            ]
        )

        base = alt.Chart(frame).encode(
            x=alt.X("day:N", title="День", sort=None),
        )
        bars = base.mark_bar(color="#4C78A8", opacity=0.85).encode(
            y=alt.Y(
                "sales_count:Q",
                title="Продаж",
                axis=alt.Axis(titleColor="#4C78A8"),
            ),
            tooltip=[
                alt.Tooltip("day:N", title="День"),
                alt.Tooltip("sales_count:Q", title="Продаж"),
                alt.Tooltip("income_sum:Q", title="Доход", format=".2f"),
            ],
        )
        line = base.mark_line(color="#F58518", point=True).encode(
            y=alt.Y(
                "income_sum:Q",
                title="Доход, ₽",
                axis=alt.Axis(titleColor="#F58518", orient="right"),
            ),
            tooltip=[
                alt.Tooltip("day:N", title="День"),
                alt.Tooltip("income_sum:Q", title="Доход", format=".2f"),
            ],
        )
        chart = (
            alt.layer(bars, line)
            .resolve_scale(y="independent")
            .properties(height=320)
        )
        st.altair_chart(chart, use_container_width=True)
