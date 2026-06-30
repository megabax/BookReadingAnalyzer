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
  storage/            # JSON, MS SQL (mssql_repo.py)
  analyze/            # сводки и reclan.csv
  pipeline/           # оркестратор sync_reads
  services/           # слой для UI (reports.py)
  cli.py              # аргументы командной строки

config/               # settings, books.yaml
scripts/              # fetch_reads.py, report.py
data/raw/             # снимки JSON
scripts/init_mssql.py # создание таблиц в MS SQL
legacy/               # старые эксперименты
selenium_stats.py     # точка входа CLI
streamlit_app.py      # веб-интерфейс (Streamlit)
```

## Установка

```bat
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Тесты: `pytest` (см. [`docs/testing_strategy.md`](docs/testing_strategy.md)).

## Запуск

```bat
REM По умолчанию — июль 2025, book_id 323389 (см. config/settings.py)
python selenium_stats.py --wait-login 60

REM По URL
python selenium_stats.py "https://author.today/report/work/stats?..."

REM По периоду (URL соберётся из AT_BOOK_ID или AT_WORK_ID)
python selenium_stats.py --book-id 323389 --start 2025-07-01 --end 2025-07-31 --wait-login 60 -o reads.csv

REM То же через scripts
python scripts/fetch_reads.py --start 2025-07-01 --end 2025-07-31 --wait-login 60
```

Скопируйте `.env.example` в `.env` и укажите `AT_EMAIL` / `AT_PASSWORD`.

При входе с нового устройства скрипт запросит код из письма в консоли и введёт его в форму.

Без `.env` — ручной вход: `python selenium_stats.py --wait-login 60`

## MS SQL Server

**Источник правды для отчётов** — MS SQL. Файлы `data/raw/reads_*.json` — устаревший артефакт (см. ADR-012 в `docs/decisions.md`).

Таблицы:

| Таблица | Назначение |
|---------|------------|
| `dbo.fetch_runs` | Снимок загрузки: work_id, период, время |
| `dbo.chapter_reads` | Прочтения: дата, глава, views (структура `dates` из JSON) |

```bat
pip install -r requirements.txt
python scripts/init_mssql.py
python selenium_stats.py
```

Параметры в `.env` — см. `.env.example`. Отключить запись в БД: `--no-mssql`.

Удалить ошибочно загруженные дубли из БД:

```bat
python scripts/delete_runs.py --book-id 323389 --fetched-from 2026-06-02T09:00:00 --fetched-to 2026-06-02T10:00:00 --dry-run
python scripts/delete_runs.py --book-id 323389 --fetched-from 2026-06-02T09:00:00 --fetched-to 2026-06-02T10:00:00 --yes
```

## Воронка по главам

Сумма просмотров за период по `chapter_order`, доля от базовой главы и от предыдущей:

```bat
python scripts/report_funnel.py --book-id 323389 --start 2025-07-01 --end 2025-07-31
python scripts/report_funnel.py --skip-book-page --base-order 2 --csv
python scripts/report_funnel.py --book-id 323389 --base-order 2 --start 2025-07-01 --end 2025-07-31
```

Для отладки по JSON (legacy): `AT_ENABLE_LEGACY_JSON=yes` и `--json data/raw/reads_....json`.

`--base-order N` — 100% считается от главы с `chapter_order=N` (порядок на сайте / в БД). Без флага — от первой главы воронки.

Флаг `--csv` / `-o` сохраняет таблицу в CSV (разделитель `;`, UTF-8 с BOM для Excel). Без имени файла — `data/reports/funnel_<book_id>_<start>_<end>.csv`.

## Веб-интерфейс (Streamlit)

Каркас UI подготовлен; полные экраны отчётов — после рефакторинга SQL/snapshot (см. `refactoring_plan.md` §18).

```bat
pip install -r requirements.txt -r requirements-ui.txt
streamlit run streamlit_app.py
```

Подробно: [`docs/ui_streamlit.md`](docs/ui_streamlit.md).

## Сравнение двух воронок (период A vs B)

По каждому дню и главе: % просмотров от базовой главы; по периоду — среднее **μ** и **σ** (по дням), для каждой главы — **p-value** (Welch t-test, двусторонний).

```bat
python scripts/report_funnel_compare.py --book-id 323389 --base-order 2 ^
  --start-a 2025-07-01 --end-a 2025-07-31 ^
  --start-b 2025-08-01 --end-b 2025-08-31 --skip-book-page --csv
```

Для отладки по JSON (legacy): `AT_ENABLE_LEGACY_JSON=yes` и `--json-a` / `--json-b`.

`*` в консоли — p < 0,05 (различие средних дневных % значимо).

## Дальнейшие шаги
- `scripts/report.py` — прочие отчёты
- [`refactoring_plan.md`](refactoring_plan.md) и [`docs/`](docs/README.md) — план и документация перед рефакторингом

172953