"""Тесты ReadSnapshot и StatsTable."""

from __future__ import annotations

from datetime import date, datetime

from author_today.domain.models import ReadSnapshot, StatsTable, parse_dd_mm_columns


def test_parse_dd_mm_columns_cross_year():
    assert parse_dd_mm_columns(["28.12", "02.01"], date(2025, 12, 1)) == (
        date(2025, 12, 28),
        date(2026, 1, 2),
    )


def test_from_stats_table_same_year():
    table = StatsTable(
        dates=["01.07", "02.07"],
        rows=[
            {"chapter": "Глава 1", "01.07": 10, "02.07": 20},
            {"chapter": "Глава 2", "01.07": 5, "02.07": 15},
        ],
    )
    snap = ReadSnapshot.from_stats_table(
        table,
        book_id=1,
        period_start=date(2025, 7, 1),
        period_end=date(2025, 7, 31),
        fetched_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    assert snap.dates == (date(2025, 7, 1), date(2025, 7, 2))
    assert snap.chapters == ("Глава 1", "Глава 2")
    assert snap.values[0] == (10, 20)
    assert snap.values[1] == (5, 15)


def test_from_stats_table_cross_year():
    table = StatsTable(
        dates=["28.12", "02.01"],
        rows=[
            {"chapter": "Глава 1", "28.12": 10, "02.01": 20},
        ],
    )
    snap = ReadSnapshot.from_stats_table(
        table,
        book_id=1,
        period_start=date(2025, 12, 1),
        period_end=date(2026, 1, 31),
    )
    assert snap.dates[0] == date(2025, 12, 28)
    assert snap.dates[1] == date(2026, 1, 2)


def test_to_document_roundtrip(minimal_snapshot: ReadSnapshot):
    doc = minimal_snapshot.to_document()
    assert doc["book_id"] == 1
    assert len(doc["dates"]) == 2
    assert doc["dates"][0]["chapters"][1]["chapter"] == "Глава 1"
    assert doc["dates"][0]["chapters"][1]["views"] == 80


def test_read_snapshot_from_json_fixture(minimal_snapshot_path):
    snap = ReadSnapshot.from_json(minimal_snapshot_path)
    assert snap.book_id == 1
    assert len(snap.dates) == 2
    assert snap.chapters[2] == "Глава 2"
    assert snap.values[2][0] == 40


def test_from_aggregated_rows():
    snap = ReadSnapshot.from_aggregated_rows(
        book_id=1,
        period_start=date(2025, 7, 1),
        period_end=date(2025, 7, 2),
        fetched_at=datetime(2026, 1, 1),
        rows=[
            (date(2025, 7, 1), 1, "Глава 1", 10),
            (date(2025, 7, 1), 2, "Глава 2", 5),
            (date(2025, 7, 2), 1, "Глава 1", 20),
            (date(2025, 7, 2), 2, "Глава 2", 15),
        ],
    )
    assert snap.chapter_orders == (1, 2)
    assert snap.chapter_totals() == [(1, "Глава 1", 30), (2, "Глава 2", 20)]
    matrix = snap.daily_matrix()
    assert matrix[date(2025, 7, 1)][1] == ("Глава 1", 10)


def test_funnel_snapshot_matches_json_path(minimal_snapshot, minimal_snapshot_path):
    """Снимок из фикстуры и воронка из JSON должны согласовываться по суммам."""
    from author_today.analyze.funnel import funnel_from_json, funnel_from_snapshot

    steps_json = funnel_from_json(minimal_snapshot_path, skip_book_page=True)
    steps_snap = funnel_from_snapshot(minimal_snapshot, skip_book_page=True)
    assert len(steps_json) == len(steps_snap)
    for a, b in zip(steps_json, steps_snap, strict=True):
        assert a.chapter_name == b.chapter_name
        assert a.total_views == b.total_views
