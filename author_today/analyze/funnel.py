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
    step_num: int  # порядковый номер в воронке (1..N)
    site_chapter_order: int  # chapter_order на сайте / в БД
    chapter_name: str
    total_views: int
    pct_of_first: float
    pct_of_previous: float | None
    drop_from_previous: int | None


def _pct(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round(100.0 * part / whole, 1)


def _pct_column_label(baseline_chapter_order: int | None) -> str:
    if baseline_chapter_order is None:
        return "% от 1-й"
    return f"% от гл.{baseline_chapter_order}"


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
    baseline_chapter_order: int | None = None,
) -> list[FunnelStep]:
    """
    Построить воронку из (chapter_order, chapter_name, total_views).
    rows должны быть отсортированы по chapter_order.
    baseline_chapter_order — с какой главы (по порядку на сайте) считать 100%% для «% от 1-й».
    """
    filtered: list[tuple[int, str, int]] = []
    for order, name, views in sorted(rows, key=lambda r: r[0]):
        if skip_book_page and name.strip().lower() == "страница книги":
            continue
        filtered.append((order, name, views))

    if not filtered:
        return []

    if baseline_chapter_order is not None:
        baseline_views = next(
            (views for order, _name, views in filtered if order == baseline_chapter_order),
            None,
        )
        if baseline_views is None:
            available = ", ".join(str(order) for order, _n, _v in filtered)
            raise ValueError(
                f"Глава с chapter_order={baseline_chapter_order} не найдена. "
                f"Доступные порядки: {available}"
            )
        first_views = baseline_views
    else:
        first_views = filtered[0][2]
    steps: list[FunnelStep] = []
    prev_views: int | None = None

    for step_num, (site_order, name, views) in enumerate(filtered, start=1):
        pct_prev = _pct(views, prev_views) if prev_views is not None else None
        drop = (prev_views - views) if prev_views is not None else None
        steps.append(
            FunnelStep(
                step_num=step_num,
                site_chapter_order=site_order,
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
    baseline_chapter_order: int | None = None,
) -> list[FunnelStep]:
    totals: list[tuple[int, str, int]] = []
    for idx, chapter in enumerate(snapshot.chapters):
        order = idx + 1
        views = sum(v or 0 for v in snapshot.values[idx])
        totals.append((order, chapter, views))
    return build_funnel(
        totals,
        skip_book_page=skip_book_page,
        baseline_chapter_order=baseline_chapter_order,
    )


def funnel_from_json(
    path: Path,
    *,
    skip_book_page: bool = False,
    baseline_chapter_order: int | None = None,
) -> list[FunnelStep]:
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
    return build_funnel(
        rows,
        skip_book_page=skip_book_page,
        baseline_chapter_order=baseline_chapter_order,
    )


def funnel_from_mssql(
    settings: Settings,
    book_id: int,
    period_start: date,
    period_end: date,
    *,
    skip_book_page: bool = False,
    baseline_chapter_order: int | None = None,
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
    return build_funnel(
        rows,
        skip_book_page=skip_book_page,
        baseline_chapter_order=baseline_chapter_order,
    )


def print_funnel(
    steps: list[FunnelStep],
    *,
    book_id: int | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    title: str = "Воронка прочтений по главам",
    baseline_chapter_order: int | None = None,
) -> None:
    if book_id is not None and period_start and period_end:
        print(f"{title} | book_id={book_id} | {period_start} — {period_end}")
    else:
        print(title)
    if baseline_chapter_order is not None:
        print(f"100%: chapter_order={baseline_chapter_order}")
    print()

    if not steps:
        print("Нет данных для воронки.")
        return

    pct_col = _pct_column_label(baseline_chapter_order)
    header = (
        f"{'#':>4}  {'Глава':<28}  {'Просмотры':>10}  "
        f"{pct_col:>12}  {'% от пред.':>11}  {'Падение':>8}"
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
            f"{step.step_num:>4}  {name:<28}  {step.total_views:>10}  "
            f"{step.pct_of_first:>8.1f}%  {pct_prev}  {drop}"
        )

    print()
    print(f"Шагов воронки: {len(steps)}")
    if baseline_chapter_order is not None:
        baseline_step = next(
            (s for s in steps if s.site_chapter_order == baseline_chapter_order),
            None,
        )
        baseline_note = (
            f"база гл.{baseline_chapter_order} ({baseline_step.total_views} просм.)"
            if baseline_step
            else f"база гл.{baseline_chapter_order}"
        )
    else:
        baseline_note = "первая глава"
    print(
        f"Просмотры: {baseline_note}, "
        f"последняя {steps[-1].total_views} "
        f"({steps[-1].pct_of_first:.1f}% от базы)"
    )


def _fmt_decimal(value: float, places: int = 1) -> str:
    """Дробная часть через запятую (для Excel в ru-RU)."""
    return f"{value:.{places}f}".replace(".", ",")


def save_funnel_csv(
    steps: list[FunnelStep],
    path: Path,
    *,
    baseline_chapter_order: int | None = None,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pct_col = _pct_column_label(baseline_chapter_order)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(
            [
                "№",
                "chapter_order",
                "Глава",
                "Просмотры",
                pct_col,
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
                    step.step_num,
                    step.site_chapter_order,
                    step.chapter_name,
                    step.total_views,
                    _fmt_decimal(step.pct_of_first),
                    pct_prev,
                    step.drop_from_previous if step.drop_from_previous is not None else "",
                ]
            )
    return path
