#!/usr/bin/env python
"""Загрузка таблицы прочтений. Запуск: python scripts/fetch_reads.py

Требуется editable-установка: pip install -e .
"""

import sys

from author_today.cli import main
from author_today.cli_reminders import run_with_manual_smoke_reminder

if __name__ == "__main__":
    sys.exit(run_with_manual_smoke_reminder(main))
