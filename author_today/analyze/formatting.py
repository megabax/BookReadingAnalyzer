"""Форматирование чисел и процентов для отчётов."""

from __future__ import annotations


def pct(part: float, whole: float, *, places: int = 1) -> float:
    """Доля part/whole в процентах; при whole <= 0 — 0.0."""
    if whole <= 0:
        return 0.0
    return round(100.0 * part / whole, places)


def pct_column_label(baseline_chapter_order: int | None) -> str:
    if baseline_chapter_order is None:
        return "% от 1-й"
    return f"% от гл.{baseline_chapter_order}"


def fmt_decimal_ru(value: float, places: int = 1) -> str:
    """Дробная часть через запятую (для Excel в ru-RU)."""
    return f"{value:.{places}f}".replace(".", ",")


def fmt_pvalue(p: float | None) -> str:
    if p is None:
        return "—"
    if p < 0.0001:
        return f"{p:.2e}".replace(".", ",")
    return fmt_decimal_ru(p, 4)
