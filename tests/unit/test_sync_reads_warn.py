"""Тест предупреждения при экспорте multi-month в один CSV/JSON."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from author_today.pipeline.sync_reads import _warn_multimonth_single_file_export


def test_warn_multimonth_export_with_csv(capsys):
    _warn_multimonth_single_file_export(
        date(2025, 7, 1),
        date(2025, 8, 31),
        output_csv=Path("out.csv"),
        output_json=None,
    )
    err = capsys.readouterr().err
    assert "Предупреждение" in err
    assert "последний месяц" in err
    assert "CSV" in err


def test_warn_multimonth_export_skipped_for_single_month(capsys):
    _warn_multimonth_single_file_export(
        date(2025, 7, 1),
        date(2025, 7, 31),
        output_csv=Path("out.csv"),
        output_json=None,
    )
    assert capsys.readouterr().err == ""
