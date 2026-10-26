"""Парсинг строк getdetailstable."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from author_today.fetch.sales_client import (
    SalesFetchError,
    parse_aspnet_datetime,
    parse_sale_event_row,
)
from author_today.fetch.sales_url import build_dashboard_url, build_details_query


def test_build_dashboard_url_contains_item_and_group():
    url = build_dashboard_url(172953, date(2026, 10, 13), date(2026, 10, 20))
    assert "merchant/dashboard" in url
    assert "groupBy=work" in url
    assert "itemId=172953" in url
    assert "startDate=" in url
    assert "endDate=" in url


def test_build_details_query_paging():
    params = build_details_query(
        172953,
        date(2026, 10, 13),
        date(2026, 10, 20),
        page=2,
        page_size=200,
    )
    assert params["page"] == 2
    assert params["pageSize"] == 200
    assert params["itemId"] == 172953
    assert params["sort"] == "ProcessedTime-desc"


def test_parse_aspnet_datetime():
    dt = parse_aspnet_datetime("/Date(1760400000000)/")
    assert isinstance(dt, datetime)
    assert dt.year >= 2025


def test_parse_sale_event_row_work_only():
    row = {
        "ProcessedTime": "/Date(1760400000000)/",
        "ItemId": 172953,
        "ItemType": 1,
        "WorkFormat": 1,
        "Price": 199.0,
        "Commission": 0.3,
        "AuthorIncome": 139.3,
        "ItemTitle": "ignored",
    }
    event = parse_sale_event_row(row, expected_book_id=172953)
    assert event is not None
    assert event.book_id == 172953
    assert event.work_format == 1
    assert event.price == 199.0
    assert event.commission == 0.3
    assert event.author_income == 139.3


def test_parse_sale_event_row_skips_reward():
    row = {
        "ProcessedTime": "/Date(1760400000000)/",
        "ItemId": 99,
        "ItemType": 2,
        "WorkFormat": None,
        "Price": 50,
        "Commission": 0.1,
        "AuthorIncome": 45,
    }
    assert parse_sale_event_row(row, expected_book_id=172953) is None


def test_parse_sale_event_row_wrong_book():
    row = {
        "ProcessedTime": "/Date(1760400000000)/",
        "ItemId": 1,
        "ItemType": 1,
        "WorkFormat": 1,
        "Price": 10,
        "Commission": 0.3,
        "AuthorIncome": 7,
    }
    with pytest.raises(SalesFetchError, match="не совпадает"):
        parse_sale_event_row(row, expected_book_id=172953)
