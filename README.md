# AutorToday

Загрузка и анализ статистики прочтений книг на [author.today](https://author.today).

## Структура

```
author_today/          # основной пакет
  domain/             # модели ReadSnapshot, StatsTable
  auth/               # авторизация (ручная / авто — заготовка)
  browser/            # Selenium Chrome
  fetch/              # URL и загрузка страницы
  parse/              # парсер Kendo Grid
  storage/            # экспорт CSV/JSON, SQLite — заготовка
  analyze/            # сводки и reclan.csv
  pipeline/           # оркестратор sync_reads
  cli.py              # аргументы командной строки

config/               # settings, books.yaml
scripts/              # fetch_reads.py, report.py
data/raw/             # снимки JSON
data/db/              # SQLite (позже)
legacy/               # старые эксперименты
selenium_stats.py     # точка входа (как раньше)
```

## Установка

```bat
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
```

## Запуск

```bat
REM По умолчанию — июль 2025, work_id 323389 (см. config/settings.py)
python selenium_stats.py --wait-login 60

REM По URL
python selenium_stats.py "https://author.today/report/work/stats?..."

REM По периоду (URL соберётся из AT_WORK_ID)
python selenium_stats.py --start 2025-07-01 --end 2025-07-31 --wait-login 60 -o reads.csv

REM То же через scripts
python scripts/fetch_reads.py --start 2025-07-01 --end 2025-07-31 --wait-login 60
```

Скопируйте `.env.example` в `.env` и укажите `AT_EMAIL` / `AT_PASSWORD`.

При входе с нового устройства скрипт запросит код из письма в консоли и введёт его в форму.

Без `.env` — ручной вход: `python selenium_stats.py --wait-login 60`

## Дальнейшие шаги
- `author_today.storage.sqlite_repo` — история прочтений в БД
- `scripts/report.py` — отчёты по накопленным данным
