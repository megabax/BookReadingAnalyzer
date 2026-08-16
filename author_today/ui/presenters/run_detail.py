"""Таблица chapter_reads одного fetch_run для UI."""

from __future__ import annotations

from datetime import date

import pandas as pd

from author_today.storage.mssql_repo import FetchRunDetail


class RunDetailPresenter:
    """Широкая матрица: строки = главы (порядок сайта), столбцы = даты."""

    def wide_dataframe(self, detail: FetchRunDetail) -> pd.DataFrame:
        if not detail.rows:
            return pd.DataFrame(columns=["order", "Глава"])

        records = [
            {
                "order": row.chapter_order if row.chapter_order is not None else 10**9,
                "Глава": row.chapter_name,
                "date": row.read_date,
                "value": row.metric_value,
            }
            for row in detail.rows
        ]
        long_df = pd.DataFrame.from_records(records)
        wide = long_df.pivot_table(
            index=["order", "Глава"],
            columns="date",
            values="value",
            aggfunc="sum",
            sort=False,
        )
        wide = wide.sort_index(level=0)
        # Столбцы дат по возрастанию
        date_cols = sorted(
            (c for c in wide.columns if isinstance(c, date)),
            key=lambda d: d,
        )
        other_cols = [c for c in wide.columns if c not in date_cols]
        wide = wide.reindex(columns=other_cols + date_cols)
        wide = wide.reset_index()
        wide = wide.rename(columns={"order": "№"})
        # Читаемые заголовки дат
        rename_dates = {
            c: c.isoformat() if isinstance(c, date) else c for c in wide.columns
        }
        wide = wide.rename(columns=rename_dates)
        # Порядок без «фиктивных» NULL-order как 10**9 — оставим как есть в №
        wide.loc[wide["№"] >= 10**9, "№"] = pd.NA
        return wide
