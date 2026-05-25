"""
Главная точка входа проекта AutorToday.

Совместимость: python selenium_stats.py [аргументы]
Рекомендуется:     python scripts/fetch_reads.py [аргументы]
"""

from author_today.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
