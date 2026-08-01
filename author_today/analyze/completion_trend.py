"""Тренд дочитывания: % выбранной главы от базы по календарным месяцам."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from author_today.analyze.chapter_filters import ChapterRow, filter_chapter_rows
from author_today.analyze.formatting import fmt_decimal_ru, pct_column_label
from author_today.analyze.funnel import FunnelStep, funnel_from_snapshot
from author_today.domain.models import ReadSnapshot
from author_today.errors import DataNotFoundError


@dataclass(frozen=True)
class CompletionTrendPoint:
    month_start: date
    month_end: date
    month_label: str
    target_chapter_order: int
    target_chapter_name: str
    target_views: float
    baseline_views: float
    pct_of_baseline: float


@dataclass(frozen=True)
class CompletionTrendReport:
    book_id: int
    period_start: date
    period_end: date
    target_chapter_order: int
    target_chapter_name: str
    baseline_chapter_order: int | None
    skip_book_page: bool
    points: tuple[CompletionTrendPoint, ...]


def list_chapter_options(
    rows: list[ChapterRow],
    *,
    skip_book_page: bool = False,
) -> list[tuple[int, str]]:
    """Список (chapter_order, name) после фильтра обложки — для выбора главы в UI."""
    filtered = filter_chapter_rows(rows, skip_book_page=skip_book_page)
    return [(order, name) for order, name, _views in filtered]


def resolve_target_chapter_order(
    rows: list[ChapterRow],
    *,
    skip_book_page: bool = False,
    target_chapter_order: int | None = None,
) -> int:
    """None → последняя глава после фильтра; иначе проверка наличия порядка."""
    options = list_chapter_options(rows, skip_book_page=skip_book_page)
    if not options:
        raise DataNotFoundError("Нет глав для тренда дочитывания за выбранный период")
    if target_chapter_order is None:
        return options[-1][0]
    if not any(order == target_chapter_order for order, _name in options):
        available = ", ".join(str(order) for order, _n in options)
        raise DataNotFoundError(
            f"Глава с chapter_order={target_chapter_order} не найдена. "
            f"Доступные порядки: {available}"
        )
    return target_chapter_order


def _baseline_views(steps: list[FunnelStep], baseline_chapter_order: int | None) -> int | None:
    if not steps:
        return None
    if baseline_chapter_order is None:
        return steps[0].total_views
    base = next(
        (s for s in steps if s.site_chapter_order == baseline_chapter_order),
        None,
    )
    return base.total_views if base is not None else None


def trend_point_from_snapshot(
    snapshot: ReadSnapshot,
    *,
    target_chapter_order: int,
    skip_book_page: bool = False,
    baseline_chapter_order: int | None = None,
) -> CompletionTrendPoint | None:
    """Точка тренда за один снимок (обычно календарный месяц). Нет главы/базы → None."""
    try:
        steps = funnel_from_snapshot(
            snapshot,
            skip_book_page=skip_book_page,
            baseline_chapter_order=baseline_chapter_order,
        )
    except DataNotFoundError:
        return None
    if not steps:
        return None

    step = next(
        (s for s in steps if s.site_chapter_order == target_chapter_order),
        None,
    )
    if step is None:
        return None

    baseline_views = _baseline_views(steps, baseline_chapter_order)
    if baseline_views is None:
        return None

    return CompletionTrendPoint(
        month_start=snapshot.period_start,
        month_end=snapshot.period_end,
        month_label=f"{snapshot.period_start:%Y-%m}",
        target_chapter_order=step.site_chapter_order,
        target_chapter_name=step.chapter_name,
        target_views=step.total_views,
        baseline_views=baseline_views,
        pct_of_baseline=step.pct_of_first,
    )


def build_completion_trend(
    monthly_snapshots: list[ReadSnapshot],
    *,
    book_id: int,
    period_start: date,
    period_end: date,
    catalog_rows: list[ChapterRow],
    target_chapter_order: int | None = None,
    skip_book_page: bool = False,
    baseline_chapter_order: int | None = None,
) -> CompletionTrendReport:
    """
    Построить тренд по месячным снимкам.
    catalog_rows — totals за весь период (для выбора главы по умолчанию и имени).
    """
    resolved = resolve_target_chapter_order(
        catalog_rows,
        skip_book_page=skip_book_page,
        target_chapter_order=target_chapter_order,
    )
    options = list_chapter_options(catalog_rows, skip_book_page=skip_book_page)
    target_name = next(name for order, name in options if order == resolved)

    points: list[CompletionTrendPoint] = []
    for snapshot in monthly_snapshots:
        point = trend_point_from_snapshot(
            snapshot,
            target_chapter_order=resolved,
            skip_book_page=skip_book_page,
            baseline_chapter_order=baseline_chapter_order,
        )
        if point is not None:
            points.append(point)

    if not points:
        raise DataNotFoundError(
            f"Нет месячных точек для chapter_order={resolved} "
            f"за {period_start} — {period_end}"
        )

    return CompletionTrendReport(
        book_id=book_id,
        period_start=period_start,
        period_end=period_end,
        target_chapter_order=resolved,
        target_chapter_name=target_name,
        baseline_chapter_order=baseline_chapter_order,
        skip_book_page=skip_book_page,
        points=tuple(points),
    )


def default_completion_trend_csv_path(
    book_id: int,
    period_start: date,
    period_end: date,
    *,
    reports_dir: Path = Path("data/reports"),
) -> Path:
    name = f"completion_trend_{book_id}_{period_start:%Y%m%d}_{period_end:%Y%m%d}.csv"
    return reports_dir / name


def save_completion_trend_csv(
    report: CompletionTrendReport,
    path: Path,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pct_col = pct_column_label(report.baseline_chapter_order)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(
            [
                "Месяц",
                "Начало",
                "Конец",
                "chapter_order",
                "Глава",
                "Просмотры",
                "База",
                pct_col,
            ]
        )
        for point in report.points:
            writer.writerow(
                [
                    point.month_label,
                    point.month_start.isoformat(),
                    point.month_end.isoformat(),
                    point.target_chapter_order,
                    point.target_chapter_name,
                    point.target_views,
                    point.baseline_views,
                    fmt_decimal_ru(point.pct_of_baseline),
                ]
            )
    return path
