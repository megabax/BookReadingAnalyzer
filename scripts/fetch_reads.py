#!/usr/bin/env python
"""Загрузка таблицы прочтений. Запуск из корня проекта: python scripts/fetch_reads.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from author_today.cli import main

if __name__ == "__main__":
    sys.exit(main())
