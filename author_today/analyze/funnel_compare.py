"""Сравнение двух воронок (два периода) по дневным % от базовой главы."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from author_today.analyze.stats_test import mean_and_sigma, welch_ttest_pvalue
from author_today.domain.models import DailyMatrix, ReadSnapshot
from author_today.storage.mssql_repo import create_mssql_repository
from config.settings import Settings


@dataclass(frozen=True)
class ChapterPeriodStats:
    site_chapter_order: int
    chapter_name: str
    mean_pct: float
    sigma_pct: float
    n_days: int
    daily_pcts: tuple[float, ...]


@dataclass(frozen=True)
class ChapterCompareRow:
    site_chapter_order: int
    chapter_name: str
    period_a: ChapterPeriodStats
    period_b: ChapterPeriodStats
    p_value: float | None
    mean_diff: float  # B - A


@dataclass(frozen=True)
class FunnelCompareReport:
    book_id: int
    period_a_start: date
    period_a_end: date
    period_b_start: date
    period_b_end: date
    baseline_chapter_order: int
    rows: tuple[ChapterCompareRow, ...]


def _is_book_page(name: str) -> bool:
    return name.strip().lower() == "страница книги"


def _daily_pct_from_matrix(
    matrix: DailyMatrix,
    *,
    baseline_chapter_order: int,
    skip_book_page: bool,
) -> dict[int, tuple[str, list[float]]]:
    """
    По каждому chapter_order — имя главы и список дневных % от базы.
    Дни с нулевыми просмотрами базовой главы пропускаются.
    """
    chapter_names: dict[int, str] = {}
    series: dict[int, list[float]] = {}

    for day_rows in sorted(matrix.items()):
        _day, by_order = day_rows
        if baseline_chapter_order not in by_order:
            continue
        baseline_name, baseline_views = by_order[baseline_chapter_order]
        if baseline_views <= 0:
            continue

        for order, (name, views) in sorted(by_order.items()):
            if skip_book_page and _is_book_page(name):
                continue
            chapter_names.setdefault(order, name)
            pct = round(100.0 * views / baseline_views, 2)
            series.setdefault(order, []).append(pct)

    result: dict[int, tuple[str, list[float]]] = {}
    for order in sorted(series):
        result[order] = (chapter_names.get(order, f"Глава {order}"), series[order])
    return result


def _stats_for_series(
    site_order: int,
    name: str,
    pcts: list[float],
) -> ChapterPeriodStats:
    mean_pct, sigma_pct, n_days = mean_and_sigma(pcts)
    return ChapterPeriodStats(
        site_chapter_order=site_order,
        chapter_name=name,
        mean_pct=mean_pct,
        sigma_pct=sigma_pct,
        n_days=n_days,
        daily_pcts=tuple(pcts),
    )


def compare_funnel_periods(
    matrix_a: DailyMatrix,
    matrix_b: DailyMatrix,
    *,
    baseline_chapter_order: int,
    skip_book_page: bool = False,
    book_id: int = 0,
    period_a_start: date | None = None,
    period_a_end: date | None = None,
    period_b_start: date | None = None,
    period_b_end: date | None = None,
) -> FunnelCompareReport:
    series_a = _daily_pct_from_matrix(
        matrix_a,
        baseline_chapter_order=baseline_chapter_order,
        skip_book_page=skip_book_page,
    )
    series_b = _daily_pct_from_matrix(
        matrix_b,
        baseline_chapter_order=baseline_chapter_order,
        skip_book_page=skip_book_page,
    )

    if baseline_chapter_order not in series_a and baseline_chapter_order not in series_b:
        orders_a = ", ".join(str(k) for k in series_a) or "—"
        orders_b = ", ".join(str(k) for k in series_b) or "—"
        raise ValueError(
            f"Базовая глава chapter_order={baseline_chapter_order} не найдена "
            f"ни в одном периоде (A: {orders_a}; B: {orders_b})."
        )

    all_orders = sorted(set(series_a) | set(series_b))
    rows: list[ChapterCompareRow] = []

    for order in all_orders:
        name_a, pcts_a = series_a.get(order, (series_b.get(order, ("",))[0], []))
        name_b, pcts_b = series_b.get(order, (series_a.get(order, ("",))[0], []))
        name = name_a or name_b or f"Глава {order}"

        stat_a = _stats_for_series(order, name, pcts_a)
        stat_b = _stats_for_series(order, name, pcts_b)
        p_val = welch_ttest_pvalue(pcts_a, pcts_b)
        mean_diff = round(stat_b.mean_pct - stat_a.mean_pct, 2)

        rows.append(
            ChapterCompareRow(
                site_chapter_order=order,
                chapter_name=name,
                period_a=stat_a,
                period_b=stat_b,
                p_value=p_val,
                mean_diff=mean_diff,
            )
        )

    def _bounds(m: DailyMatrix) -> tuple[date, date]:
        if not m:
            return date.today(), date.today()
        keys = sorted(m)
        return keys[0], keys[-1]

    a0, a1 = _bounds(matrix_a)
    b0, b1 = _bounds(matrix_b)

    return FunnelCompareReport(
        book_id=book_id,
        period_a_start=period_a_start or a0,
        period_a_end=period_a_end or a1,
        period_b_start=period_b_start or b0,
        period_b_end=period_b_end or b1,
        baseline_chapter_order=baseline_chapter_order,
        rows=tuple(rows),
    )


def daily_matrix_from_snapshot(snapshot: ReadSnapshot) -> DailyMatrix:
    return snapshot.daily_matrix()


def daily_matrix_from_json(path: Path) -> DailyMatrix:
    return daily_matrix_from_snapshot(ReadSnapshot.from_json(path))


def daily_matrix_from_mssql(
    settings: Settings,
    book_id: int,
    period_start: date,
    period_end: date,
) -> DailyMatrix:
    snapshot = create_mssql_repository(settings).load_snapshot(
        book_id, period_start, period_end
    )
    return daily_matrix_from_snapshot(snapshot)


def _fmt_decimal(value: float, places: int = 2) -> str:
    return f"{value:.{places}f}".replace(".", ",")


def _fmt_pvalue(p: float | None) -> str:
    if p is None:
        return "—"
    if p < 0.0001:
        return f"{p:.2e}".replace(".", ",")
    return _fmt_decimal(p, 4)


def print_funnel_compare(report: FunnelCompareReport, *, label_a: str = "A", label_b: str = "B") -> None:
    print(
        f"Сравнение воронок | book_id={report.book_id} | "
        f"база: chapter_order={report.baseline_chapter_order}"
    )
    print(f"  {label_a}: {report.period_a_start} — {report.period_a_end}")
    print(f"  {label_b}: {report.period_b_start} — {report.period_b_end}")
    print()
    print(
        "Для каждого дня: % главы = просмотры_главы / просмотры_базы × 100. "
        "σ — несмещённое s по дням. p-value — Welch t-test (двусторонний)."
    )
    print()

    header = (
        f"{'ord':>4}  {'Глава':<24}  "
        f"{'μ A':>7} {'σ A':>6} {'n A':>4}  "
        f"{'μ B':>7} {'σ B':>6} {'n B':>4}  "
        f"{'Δμ B-A':>8}  {'p-value':>10}"
    )
    print(header)
    print("-" * len(header))

    for row in report.rows:
        name = row.chapter_name
        if len(name) > 24:
            name = name[:21] + "..."
        sig = ""
        if row.p_value is not None and row.p_value < 0.05:
            sig = "*"
        print(
            f"{row.site_chapter_order:>4}  {name:<24}  "
            f"{row.period_a.mean_pct:>7.2f} {row.period_a.sigma_pct:>6.2f} {row.period_a.n_days:>4}  "
            f"{row.period_b.mean_pct:>7.2f} {row.period_b.sigma_pct:>6.2f} {row.period_b.n_days:>4}  "
            f"{row.mean_diff:>+8.2f}  {_fmt_pvalue(row.p_value):>10}{sig}"
        )

    print()
    print("* p < 0,05 — различие средних по дням статистически значимо (Welch t-test)")


def save_funnel_compare_csv(report: FunnelCompareReport, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(
            [
                "chapter_order",
                "Глава",
                "μ_A",
                "σ_A",
                "n_A",
                "μ_B",
                "σ_B",
                "n_B",
                "Δμ_B_minus_A",
                "p_value",
                "significant_005",
            ]
        )
        for row in report.rows:
            writer.writerow(
                [
                    row.site_chapter_order,
                    row.chapter_name,
                    _fmt_decimal(row.period_a.mean_pct),
                    _fmt_decimal(row.period_a.sigma_pct),
                    row.period_a.n_days,
                    _fmt_decimal(row.period_b.mean_pct),
                    _fmt_decimal(row.period_b.sigma_pct),
                    row.period_b.n_days,
                    _fmt_decimal(row.mean_diff),
                    _fmt_pvalue(row.p_value),
                    "да" if row.p_value is not None and row.p_value < 0.05 else "",
                ]
            )
    return path
