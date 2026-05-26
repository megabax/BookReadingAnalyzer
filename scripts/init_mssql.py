#!/usr/bin/env python
"""Создание таблиц в MS SQL. Запуск: python scripts/init_mssql.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from author_today.storage.mssql_repo import create_mssql_repository
from config.settings import Settings


def main() -> int:
    settings = Settings.from_env()
    if not settings.has_mssql():
        print("Ошибка: задайте параметры MS SQL в .env (см. .env.example)", file=sys.stderr)
        return 1
    repo = create_mssql_repository(settings)
    repo.ensure_schema()
    print("Таблицы dbo.fetch_runs и dbo.chapter_reads готовы.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
