"""Тесты презентера просмотра fetch_run."""

from __future__ import annotations

from datetime import date, datetime

from author_today.storage.mssql_repo import FetchRunDetail, FetchRunReadRow
from author_today.ui.presenters.run_detail import RunDetailPresenter


def test_wide_dataframe_orders_chapters():
    detail = FetchRunDetail(
        run_id=1,
        book_id=10,
        period_start=date(2025, 7, 1),
        period_end=date(2025, 7, 2),
        fetched_at=datetime(2026, 1, 1),
        value_type="hit",
        rows=(
            FetchRunReadRow(2, "Глава 2", date(2025, 7, 1), 5),
            FetchRunReadRow(1, "Глава 1", date(2025, 7, 1), 10),
            FetchRunReadRow(1, "Глава 1", date(2025, 7, 2), 3),
        ),
    )
    wide = RunDetailPresenter().wide_dataframe(detail)

    assert list(wide["Глава"]) == ["Глава 1", "Глава 2"]
    assert "2025-07-01" in wide.columns
    assert "2025-07-02" in wide.columns
    assert float(wide.loc[wide["Глава"] == "Глава 1", "2025-07-01"].iloc[0]) == 10.0
