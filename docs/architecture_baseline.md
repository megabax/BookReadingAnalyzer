# Архитектура (базовая линия)

Снимок архитектуры **до рефакторинга** (весна 2026).

## Назначение системы

Загрузка статистики прочтений с [author.today](https://author.today) (Kendo Grid через Selenium), сохранение в **MS SQL** (источник правды для отчётов) и опционально в JSON (`data/raw/`, legacy), построение отчётов (воронка, сравнение периодов).

## Слои

```
selenium_stats.py / scripts/*
        │
        ▼
   author_today/cli.py          ← загрузка (CLI)
   scripts/report_*.py          ← отчёты (отдельные entry points)
        │
        ▼
   pipeline/sync_reads.py      ← оркестрация загрузки
        │
   ┌────┴────┬──────────┬────────────┐
   ▼         ▼          ▼            ▼
 auth/    fetch/     parse/      storage/
 browser/           kendo_grid   export, persist, mssql_repo
        │
        ▼
   analyze/                     ← funnel, funnel_compare, hypothesis_tests, formatting
        │
        ▼
   domain/models.py             ← StatsTable, ReadSnapshot
```

## Поток загрузки

1. `cli.main()` → `sync_reads()` или `sync_reads_by_period()`
2. При периоде > 1 календарного месяца — `split_period_into_months()`, цикл по chunks в **одной** сессии браузера
3. `build_stats_url(book_id, start, end)` → Selenium → `load_stats_table()` → `StatsTable`
4. `ReadSnapshot.from_stats_table()` → `persist_snapshot()`:
   - JSON: `data/raw/reads_{book_id}_{timestamp}.json`
   - MS SQL: `fetch_runs` + `chapter_reads` (если настроен `.env`)

## Поток отчётов

**Источник правды:** MS SQL. JSON — legacy (`AT_ENABLE_LEGACY_JSON=yes` для `--json` в CLI).

### Воронка (`report_funnel.py`)

```
MS SQL ─────► mssql_repo.load_snapshot() ──► ReadSnapshot ──► funnel_from_snapshot() ──► print / CSV
```

### Сравнение (`report_funnel_compare.py`)

```
MS SQL A/B ► load_snapshot() ──► daily_matrix() ──► compare_funnel_periods() ──► print / CSV
         └──► hypothesis_tests.welch_ttest_pvalue() по каждой главе
```

**Legacy (скрыто):** `funnel_from_json` / `daily_matrix_from_json` — разные парсеры, только для тестов и отладки (см. `known_issues.md`, ADR-012).

## Storage

| Компонент | Роль |
|-----------|------|
| `export.py` | CSV/JSON таблицы с сайта, печать |
| `persist.py` | Снимок → raw JSON + опционально MSSQL |
| `mssql_repo.py` | `ensure_schema`, `save_snapshot`, `list_runs`, `load_snapshot`, `delete_runs_by_fetched_at` |
| `mssql/connection.py` | pyodbc, connection string из `Settings` |
| `base.py` | Protocol `ReadRepository` (используется частично) |

## Конфигурация

- `config/settings.py` — `.env`, `book_id`, MSSQL, таймауты
- `config/books.yaml` — **не подключён** к коду

## Точки входа

| Команда | Модуль |
|---------|--------|
| `python selenium_stats.py` | `author_today.cli.main` |
| `python scripts/fetch_reads.py` | то же |
| `python scripts/init_mssql.py` | создание таблиц |
| `python scripts/report_funnel.py` | воронка |
| `python scripts/report_funnel_compare.py` | сравнение периодов |
| `python scripts/delete_runs.py` | удаление из БД |

Раньше `scripts/*` дублировали `sys.path.insert(ROOT)`; с `pyproject.toml` пакет ставится через `pip install -e .`.

## Зависимости

- Selenium 4, pandas, pyodbc, requests/bs4 (legacy)
- scipy — **опционально** (только для p-value, fallback в `hypothesis_tests.py`)

## Что не входит в основной пакет

- `legacy/` — старые эксперименты, не импортируются
- продажи / `reclan.csv` — вне текущего scope (модуль `analyze/sales.py` удалён)
