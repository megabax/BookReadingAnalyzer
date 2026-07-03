"""Напоминания в CLI (ручной smoke перед UI)."""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import TextIO

MANUAL_SMOKE_REMINDER = """\
┌─ Памятка: ручной smoke перед Streamlit UI ─────────────────────────────
│ После загрузки / отчётов сверьте MS SQL на своей книге (book_id):
│   python scripts/report_funnel.py --book-id ID --start YYYY-MM-DD --end YYYY-MM-DD
│   python scripts/report_funnel_compare.py --book-id ID --base-order N \\
│     --start-a ... --end-a ... --start-b ... --end-b ...
│ Эталон — CSV в data/reports/. Чеклист: docs/pre_refactor_checklist.md
└────────────────────────────────────────────────────────────────────────"""


def print_manual_smoke_reminder(*, stream: TextIO | None = None) -> None:
    out = stream or sys.stderr
    print(MANUAL_SMOKE_REMINDER, file=out)


def run_with_manual_smoke_reminder(main: Callable[[], int]) -> int:
    """Вызвать main() с памяткой в начале и в конце."""
    print_manual_smoke_reminder()
    exit_code = main()
    print_manual_smoke_reminder()
    return exit_code
