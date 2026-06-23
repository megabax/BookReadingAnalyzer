"""Тесты build_funnel и воронки."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from author_today.analyze.funnel import (
    build_funnel,
    default_funnel_csv_path,
    funnel_from_json,
    funnel_from_snapshot,
    save_funnel_csv,
)
from author_today.domain.models import ReadSnapshot


def test_build_funnel_basic():
    rows = [
        (1, "Страница книги", 100),
        (2, "Глава 1", 80),
        (3, "Глава 2", 40),
    ]
    steps = build_funnel(rows)
    assert len(steps) == 3
    assert steps[0].chapter_name == "Страница книги"
    assert steps[0].pct_of_first == 100.0
    assert steps[1].pct_of_first == 80.0
    assert steps[2].pct_of_previous == 50.0
    assert steps[2].drop_from_previous == 40


def test_build_funnel_skip_book_page():
    rows = [
        (1, "Страница книги", 100),
        (2, "Глава 1", 80),
        (3, "Глава 2", 40),
    ]
    steps = build_funnel(rows, skip_book_page=True)
    assert len(steps) == 2
    assert steps[0].step_num == 1
    assert steps[0].site_chapter_order == 2
    assert steps[0].chapter_name == "Глава 1"
    assert steps[0].pct_of_first == 100.0


def test_build_funnel_base_order():
    rows = [
        (1, "Страница книги", 100),
        (2, "Глава 1", 80),
        (3, "Глава 2", 40),
    ]
    steps = build_funnel(rows, skip_book_page=True, baseline_chapter_order=2)
    ch1 = next(s for s in steps if s.site_chapter_order == 2)
    ch2 = next(s for s in steps if s.site_chapter_order == 3)
    assert ch1.pct_of_first == 100.0
    assert ch2.pct_of_first == 50.0


def test_build_funnel_missing_base_raises():
    rows = [(2, "Глава 1", 80)]
    with pytest.raises(ValueError, match="chapter_order=99"):
        build_funnel(rows, baseline_chapter_order=99)


def test_funnel_from_snapshot(minimal_snapshot: ReadSnapshot):
    steps = funnel_from_snapshot(minimal_snapshot, skip_book_page=True, baseline_chapter_order=2)
    ch2 = next(s for s in steps if s.site_chapter_order == 3)
    # день1: 40/80=50%, день2: 25/50=50% → сумма 65, база 130 → 50%
    assert ch2.total_views == 65
    assert ch2.pct_of_first == 50.0


def test_funnel_from_json(minimal_snapshot_path: Path):
    steps = funnel_from_json(minimal_snapshot_path, skip_book_page=True, baseline_chapter_order=2)
    assert len(steps) == 2
    ch2 = next(s for s in steps if s.chapter_name == "Глава 2")
    assert ch2.total_views == 65


def test_default_funnel_csv_path():
    path = default_funnel_csv_path(172953, date(2025, 7, 1), date(2025, 7, 31))
    assert path.name == "funnel_172953_20250701_20250731.csv"
    assert path.parent.name == "reports"


def test_save_funnel_csv_decimal_comma(tmp_path: Path, minimal_snapshot_path: Path):
    steps = funnel_from_json(minimal_snapshot_path, skip_book_page=True, baseline_chapter_order=2)
    out = save_funnel_csv(steps, tmp_path / "f.csv", baseline_chapter_order=2)
    text = out.read_text(encoding="utf-8-sig")
    assert "50,0" in text or "50,0" in text.replace("100,0", "")
    assert ";" in text
    assert "chapter_order" in text
