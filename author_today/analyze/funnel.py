"""Воронка прочтений по порядку глав на сайте."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from author_today.domain.models import ReadSnapshot
from author_today.storage.mssql.connection import connect
from config.settings import Settings


@dataclass(frozen=True)
class FunnelStep:
    chapter_order: int
    chapter_name: str
    total_views: int
    pct_of_first: float
    pct_of_previous: float | None
    drop_from_previous: int | None


def _pct(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round(100.0 * part / whole, 1)


def default_funnel_csv_path(
    book_id: int,
    period_start: date,
    period_end: date,
    *,
    reports_dir: Path = Path("data/reports"),
) -> Path:
    name = f"funnel_{book_id}_{period_start:%Y%m%d}_{period_end:%Y%m%d}.csv"
    return reports_dir / name


def build_funnel(
    rows: list[tuple[int, str, int]],
    *,
    skip_book_page: bool = False,
) -> list[FunnelStep]:
    """
    Построить воронку из (chapter_order, chapter_name, total_views).
    rows должны быть отсортированы по chapter_order.
    """
    filtered: list[tuple[int, str, int]] = []
    for order, name, views in sorted(rows, key=lambda r: r[0]):
        if skip_book_page and name.strip().lower() == "страница книги":
            continue
        filtered.append((order, name, views))

    if not filtered:
        return []

    first_views = filtered[0][2]
    steps: list[FunnelStep] = []
    prev_views: int | None = None

    for step_num, (_order, name, views) in enumerate(filtered, start=1):
        pct_prev = _pct(views, prev_views) if prev_views is not None else None
        drop = (prev_views - views) if prev_views is not None else None
        steps.append(
            FunnelStep(
                chapter_order=step_num,
                chapter_name=name,
                total_views=views,
                pct_of_first=_pct(views, first_views),
                pct_of_previous=pct_prev,
                drop_from_previous=drop,
            )
        )
        prev_views = views

    return steps


def funnel_from_snapshot(
    snapshot: ReadSnapshot,
    *,
    skip_book_page: bool = False,
) -> list[FunnelStep]:
    totals: list[tuple[int, str, int]] = []
    for idx, chapter in enumerate(snapshot.chapters):
        order = idx + 1
        views = sum(v or 0 for v in snapshot.values[idx])
        totals.append((order, chapter, views))
    return build_funnel(totals, skip_book_page=skip_book_page)


def funnel_from_json(path: Path, *, skip_book_page: bool = False) -> list[FunnelStep]:
    data = json.loads(path.read_text(encoding="utf-8"))
    totals: dict[str, int] = {}
    chapter_names: list[str] = []
    seen: set[str] = set()

    for day in data.get("dates", []):
        for ch in day.get("chapters", []):
            name = str(ch["chapter"])
            views = int(ch.get("views") or 0)
            totals[name] = totals.get(name, 0) + views
            if name not in seen:
                seen.add(name)
                chapter_names.append(name)

    rows = [(idx + 1, name, totals[name]) for idx, name in enumerate(chapter_names)]
    return build_funnel(rows, skip_book_page=skip_book_page)


def funnel_from_mssql(
    settings: Settings,
    book_id: int,
    period_start: date,
    period_end: date,
    *,
    skip_book_page: bool = False,
) -> list[FunnelStep]:
    sql = """
        SELECT
            cr.chapter_order,
            cr.chapter_name,
            SUM(COALESCE(cr.views, 0)) AS total_views
        FROM dbo.chapter_reads cr
        INNER JOIN dbo.fetch_runs fr ON fr.id = cr.run_id
        WHERE fr.work_id = ?
          AND cr.read_date >= ?
          AND cr.read_date <= ?
        GROUP BY cr.chapter_order, cr.chapter_name
        ORDER BY cr.chapter_order
    """
    with connect(settings) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, book_id, period_start, period_end)
        rows = [(int(r[0]), str(r[1]), int(r[2])) for r in cursor.fetchall()]
    return build_funnel(rows, skip_book_page=skip_book_page)


def print_funnel(
    steps: list[FunnelStep],
    *,
    book_id: int | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    title: str = "Воронка прочтений по главам",
) -> None:
    if book_id is not None and period_start and period_end:
        print(f"{title} | book_id={book_id} | {period_start} — {period_end}")
    else:
        print(title)
    print()

    if not steps:
        print("Нет данных для воронки.")
        return

    header = (
        f"{'#':>4}  {'Глава':<28}  {'Просмотры':>10}  "
        f"{'% от 1-й':>9}  {'% от пред.':>11}  {'Падение':>8}"
    )
    print(header)
    print("-" * len(header))

    for step in steps:
        if step.pct_of_previous is not None:
            pct_prev = f"{step.pct_of_previous:>9.1f}%"
        else:
            pct_prev = f"{'—':>10}"
        drop = (
            f"{step.drop_from_previous:>8}"
            if step.drop_from_previous is not None
            else f"{'—':>8}"
        )
        name = step.chapter_name
        if len(name) > 28:
            name = name[:25] + "..."
        print(
            f"{step.chapter_order:>4}  {name:<28}  {step.total_views:>10}  "
            f"{step.pct_of_first:>8.1f}%  {pct_prev}  {drop}"
        )

    print()
    print(f"Шагов воронки: {len(steps)}")
    print(
        f"Просмотры: первая глава {steps[0].total_views}, "
        f"последняя {steps[-1].total_views} "
        f"({steps[-1].pct_of_first:.1f}% от первой)"
    )


def _fmt_decimal(value: float, places: int = 1) -> str:
    """Дробная часть через запятую (для Excel в ru-RU)."""
    return f"{value:.{places}f}".replace(".", ",")


def save_funnel_csv(steps: list[FunnelStep], path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(
            [
                "№",
                "Глава",
                "Просмотры",
                "% от 1-й",
                "% от пред.",
                "Падение",
            ]
        )
        for step in steps:
            pct_prev = (
                _fmt_decimal(step.pct_of_previous)
                if step.pct_of_previous is not None
                else ""
            )
            writer.writerow(
                [
                    step.chapter_order,
                    step.chapter_name,
                    step.total_views,
                    _fmt_decimal(step.pct_of_first),
                    pct_prev,
                    step.drop_from_previous if step.drop_from_previous is not None else "",
                ]
            )
    return path
