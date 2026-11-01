"""Презентация отчёта по продажам."""

from __future__ import annotations

import pandas as pd

from author_today.services.sales import (
    SalesChartPoint,
    SalesGroupBy,
    work_format_label,
)
from author_today.storage.mssql_repo import SalesPeriodReport


class SalesPresenter:
    def metrics(self, report: SalesPeriodReport) -> None:
        import streamlit as st

        c1, c2, c3 = st.columns(3)
        c1.metric("Продаж", report.sales_count)
        c2.metric("Доход автора, ₽", f"{report.income_sum:,.2f}".replace(",", " "))
        c3.metric("Сумма цен, ₽", f"{report.price_sum:,.2f}".replace(",", " "))

    def events_table(self, report: SalesPeriodReport) -> None:
        import streamlit as st

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
    def render(
        self,
        points: list[SalesChartPoint],
        *,
        group_by: SalesGroupBy = "day",
    ) -> None:
        import altair as alt
        import streamlit as st

        if not points:
            st.caption("Нет точек для графика.")
            return

        if group_by == "day":
            x_title = "День"
        elif group_by == "week":
            x_title = "Неделя"
        else:
            x_title = "Месяц"

        frame = pd.DataFrame(
            [
                {
                    "label": p.label,
                    "sales_count": p.sales_count,
                    "income_sum": p.income_sum,
                }
                for p in points
            ]
        )

        base = alt.Chart(frame).encode(
            x=alt.X("label:N", title=x_title, sort=None),
        )
        bars = base.mark_bar(color="#4C78A8", opacity=0.85).encode(
            y=alt.Y(
                "sales_count:Q",
                title="Продаж",
                axis=alt.Axis(titleColor="#4C78A8"),
            ),
            tooltip=[
                alt.Tooltip("label:N", title=x_title),
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
                alt.Tooltip("label:N", title=x_title),
                alt.Tooltip("income_sum:Q", title="Доход", format=".2f"),
            ],
        )
        chart = (
            alt.layer(bars, line)
            .resolve_scale(y="independent")
            .properties(height=320)
        )
        st.altair_chart(chart, use_container_width=True)

