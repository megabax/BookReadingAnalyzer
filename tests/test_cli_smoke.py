"""Smoke-тесты CLI скриптов (без Selenium и БД)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _run_script(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    return subprocess.run(
        [sys.executable, str(ROOT / script), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
        env=env,
    )


def test_report_funnel_help():
    result = _run_script("scripts/report_funnel.py", "--help")
    assert result.returncode == 0
    assert "--base-order" in result.stdout


def test_report_funnel_compare_help():
    result = _run_script("scripts/report_funnel_compare.py", "--help")
    assert result.returncode == 0
    assert "--start-a" in result.stdout


def test_delete_runs_help():
    result = _run_script("scripts/delete_runs.py", "--help")
    assert result.returncode == 0
    assert "--book-id" in result.stdout


def test_report_funnel_json_fixture(minimal_snapshot_path: Path):
    result = _run_script(
        "scripts/report_funnel.py",
        "--json",
        str(minimal_snapshot_path),
        "--skip-book-page",
        "--base-order",
        "2",
    )
    assert result.returncode == 0, result.stderr
    assert "book_id=1" in result.stdout
    assert "50.0%" in result.stdout


def test_report_funnel_compare_json_fixture(minimal_snapshot_path: Path):
    result = _run_script(
        "scripts/report_funnel_compare.py",
        "--json-a",
        str(minimal_snapshot_path),
        "--json-b",
        str(minimal_snapshot_path),
        "--start-a",
        "2025-07-01",
        "--end-a",
        "2025-07-02",
        "--start-b",
        "2025-07-01",
        "--end-b",
        "2025-07-02",
        "--base-order",
        "2",
        "--skip-book-page",
    )
    assert result.returncode == 0, result.stderr
    assert "chapter_order=2" in result.stdout
    assert "50.00" in result.stdout
