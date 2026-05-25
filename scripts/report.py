#!/usr/bin/env python
"""Отчёты по сохранённым данным (заготовка)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    print("report.py — будет формировать статистику из data/raw и БД.")
    print("Пока используйте author_today.analyze.reads.summary_from_table")
    return 0


if __name__ == "__main__":
    sys.exit(main())
