"""Unit-тесты для author_today.cli_common."""

from __future__ import annotations

import argparse

from author_today.cli_common import (
    add_book_id_arg,
    add_csv_output_arg,
    add_funnel_filter_args,
    add_period_args,
    resolve_book_id,
)
from config.settings import Settings


def test_add_book_id_and_resolve():
    parser = argparse.ArgumentParser()
    add_book_id_arg(parser)
    args = parser.parse_args(["--book-id", "42"])
    settings = Settings(book_id=1)
    assert resolve_book_id(args, settings) == 42

    args_default = parser.parse_args([])
    assert resolve_book_id(args_default, settings) == 1


def test_add_funnel_filter_and_csv_destinations():
    parser = argparse.ArgumentParser()
    add_funnel_filter_args(parser)
    add_csv_output_arg(parser, options=("-o", "--output", "--csv"))
    args = parser.parse_args(["--skip-book-page", "--base-order", "2", "-o"])
    assert args.skip_book_page is True
    assert args.base_order == 2
    assert args.csv is not None
    assert args.csv.name == ""


def test_add_period_args_with_custom_names():
    parser = argparse.ArgumentParser()
    add_period_args(
        parser,
        start_dest="start_a",
        end_dest="end_a",
        start_option="--start-a",
        end_option="--end-a",
        required=True,
    )
    args = parser.parse_args(["--start-a", "2025-07-01", "--end-a", "2025-07-31"])
    assert args.start_a == "2025-07-01"
    assert args.end_a == "2025-07-31"
