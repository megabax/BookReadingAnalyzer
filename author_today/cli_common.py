"""Общие argparse-хелперы для scripts/ и CLI-отчётов."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from config.settings import Settings


def add_book_id_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--book-id", type=int, help="ID книги (AT_BOOK_ID / AT_WORK_ID)")


def add_period_args(
    parser: argparse.ArgumentParser,
    *,
    start_dest: str = "start",
    end_dest: str = "end",
    start_option: str = "--start",
    end_option: str = "--end",
    start_help: str = "Начало периода YYYY-MM-DD",
    end_help: str = "Конец периода YYYY-MM-DD",
    required: bool = False,
) -> None:
    parser.add_argument(start_option, dest=start_dest, type=str, required=required, help=start_help)
    parser.add_argument(end_option, dest=end_dest, type=str, required=required, help=end_help)


def add_funnel_filter_args(
    parser: argparse.ArgumentParser,
    *,
    base_order_required: bool = False,
    skip_book_page_help: str = "Не включать «Страница книги» в воронку",
    base_order_help: str = (
        "chapter_order главы, от которой считать 100%% (по умолчанию — первая в воронке)"
    ),
) -> None:
    parser.add_argument(
        "--skip-book-page",
        action="store_true",
        help=skip_book_page_help,
    )
    kwargs: dict = {
        "type": int,
        "required": base_order_required,
        "help": base_order_help,
    }
    if not base_order_required:
        kwargs["metavar"] = "N"
    parser.add_argument("--base-order", **kwargs)


def add_csv_output_arg(
    parser: argparse.ArgumentParser,
    *,
    options: Sequence[str] = ("--csv",),
    help: str = "Сохранить сводку в CSV",
) -> None:
    parser.add_argument(
        *options,
        dest="csv",
        nargs="?",
        const=Path(""),
        default=None,
        type=Path,
        metavar="PATH",
        help=help,
    )


def resolve_book_id(args: argparse.Namespace, settings: Settings) -> int:
    return args.book_id if args.book_id is not None else settings.book_id


def require_legacy_json(settings: Settings, *, flags: str) -> bool:
    """True, если legacy JSON разрешён; иначе печатает ошибку и возвращает False."""
    if settings.enable_legacy_json:
        return True
    print(
        f"Ошибка: {flags} отключены (источник правды — MS SQL). "
        "Для отладки: AT_ENABLE_LEGACY_JSON=yes",
        file=sys.stderr,
    )
    return False


def require_mssql(settings: Settings) -> bool:
    """True, если MS SQL настроен; иначе печатает ошибку и возвращает False."""
    if settings.has_mssql():
        return True
    print(
        "Ошибка: настройте MS SQL в .env (источник данных для отчётов)",
        file=sys.stderr,
    )
    return False


def print_error(message: object) -> None:
    print(f"Ошибка: {message}", file=sys.stderr)
