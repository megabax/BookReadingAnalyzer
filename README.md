# AutorToday

Загрузка и анализ статистики прочтений книг на [author.today](https://author.today).

## Структура

```
author_today/             # основной пакет
  domain/                # ReadSnapshot, StatsTable
  auth/                  # авторизация (ручная / AT_EMAIL)
  browser/               # Selenium Chrome
  fetch/                 # URL, периоды, загрузка страницы
  parse/                 # парсер Kendo Grid
  storage/               # MS SQL (mssql_repo), JSON export
  analyze/               # воронка, compare, hypothesis_tests
  pipeline/              # sync_reads
  services/              # слой для Streamlit (reports, fetch, books)
  cli.py / cli_common.py # CLI загрузки и общие argparse-хелперы

config/                  # settings, books.yaml
scripts/                 # fetch_reads, report_funnel*, delete_runs, init_mssql, …
data/raw/                # legacy JSON-снимки (опционально)
data/reports/            # CSV отчётов
legacy/                  # старые эксперименты (не в пакете)
selenium_stats.py        # точка входа CLI (загрузка)
streamlit_app.py         # веб-интерфейс
tests/                   # pytest
```

## Установка

```bat
python -m venv venv
venv\Scripts\activate.bat
pip install -e ".[dev]"
```

Editable-установка (`-e`) регистрирует пакеты `author_today` и `config` в окружении — скрипты и `selenium_stats.py` работают без хаков с `sys.path`.

Альтернатива (зависимости без editable): `pip install -r requirements.txt -r requirements-dev.txt`.

UI: `pip install -e ".[ui]"` или `pip install -r requirements-ui.txt`.

Тесты: `pytest` (см. [`docs/testing_strategy.md`](docs/testing_strategy.md)).

## Запуск

```bat
REM Период по умолчанию — прошлый месяц (см. config/settings.py)
python selenium_stats.py --wait-login 60

REM По URL
python selenium_stats.py "https://author.today/report/work/stats?..."

REM По периоду (URL соберётся из AT_BOOK_ID)
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
pip install -e .
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

## Сравнение двух воронок (период A vs B)

По каждому дню и главе: % просмотров от базовой главы; по периоду — среднее **μ** и **σ** (по дням), для каждой главы — **p-value** (Welch t-test, двусторонний).

```bat
python scripts/report_funnel_compare.py --book-id 323389 --base-order 2 ^
  --start-a 2025-07-01 --end-a 2025-07-31 ^
  --start-b 2025-08-01 --end-b 2025-08-31 --skip-book-page --csv
```

Для отладки по JSON (legacy): `AT_ENABLE_LEGACY_JSON=yes` и `--json-a` / `--json-b`.

`*` в консоли — p < 0,05 (различие средних дневных % значимо).

## Веб-интерфейс (Streamlit)

Рабочие вкладки: загрузка, воронка, сравнение периодов.

```bat
pip install -e ".[ui]"
streamlit run streamlit_app.py
```

Подробно: [`docs/ui_streamlit.md`](docs/ui_streamlit.md).

## Документация

- [`refactoring_plan.md`](refactoring_plan.md) — план рефакторинга
- [`docs/`](docs/README.md) — глоссарий, ADR, known issues, стратегия тестов
