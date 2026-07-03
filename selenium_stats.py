"""
Главная точка входа проекта AutorToday.

Совместимость: python selenium_stats.py [аргументы]
Рекомендуется:     python scripts/fetch_reads.py [аргументы]
"""

from author_today.cli import main

if __name__ == "__main__":
    from author_today.cli_reminders import run_with_manual_smoke_reminder

    raise SystemExit(run_with_manual_smoke_reminder(main))
