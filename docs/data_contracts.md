# Контракты данных

Форматы, которые **нельзя менять без миграции** и обновления тестов.

## JSON снимок (`data/raw/reads_*.json`)

Корневой объект:

```json
{
  "book_id": 323389,
  "period_start": "2025-07-01",
  "period_end": "2025-07-31",
  "fetched_at": "2026-05-27T16:16:03",
  "dates": [
    {
      "date": "2025-07-01",
      "chapters": [
        { "chapter": "Страница книги", "views": 12 },
        { "chapter": "Глава 1", "views": 5 }
      ]
    }
  ]
}
```

| Поле | Тип | Правила |
|------|-----|---------|
| `book_id` | int | ID книги на author.today |
| `period_start`, `period_end` | ISO date | Границы запроса |
| `fetched_at` | ISO datetime | Время сохранения |
| `dates[].date` | ISO date | День наблюдения |
| `dates[].chapters[].chapter` | string | Название как на сайте |
| `dates[].chapters[].views` | int \| null | Просмотры; null трактуется как 0 в отчётах |

**Порядок глав:** позиция в массиве `chapters` = `chapter_order` (1-based). Поле `chapter_order` в JSON **не записывается** (`to_document()`).

## MS SQL

### `dbo.books`

| Колонка | Тип | Описание |
|---------|-----|----------|
| `id` | INT PK | = `book_id` / workId |
| `title` | NVARCHAR(300) NULL | Не заполняется автоматически |
| `created_at` | DATETIME2 | UTC |

### `dbo.fetch_runs`

| Колонка | Тип | Описание |
|---------|-----|----------|
| `id` | BIGINT IDENTITY PK | `run_id` |
| `work_id` | INT FK → books.id | |
| `period_start`, `period_end` | DATE | |
| `fetched_at` | DATETIME2 | |

### `dbo.chapter_reads`

| Колонка | Тип | Описание |
|---------|-----|----------|
| `run_id` | BIGINT FK | ON DELETE CASCADE |
| `read_date` | DATE | |
| `chapter_order` | INT | Порядок на сайте |
| `chapter_name` | NVARCHAR(500) | |
| `views` | INT NULL | |

PK: `(run_id, read_date, chapter_name)`.

При нескольких `fetch_runs` за один период аналитика **суммирует** `views` (риск дублей — см. `delete_runs.py`).

## CSV воронки

- Кодировка: UTF-8 с BOM
- Разделитель полей: `;`
- Дробная часть: **запятая** (ru-RU)
- Колонки: `№`, `chapter_order`, `Глава`, `Просмотры`, `% от 1-й` / `% от гл.N`, `% от пред.`, `Падение`

## CSV сравнения воронок

- Те же правила кодировки и разделителя
- Колонки: `chapter_order`, `Глава`, `μ_A`, `σ_A`, `n_A`, `μ_B`, `σ_B`, `n_B`, `Δμ_B_minus_A`, `p_value`, `significant_005`

## CLI: общие флаги отчётов

| Флаг | Отчёты | Описание |
|------|--------|----------|
| `--book-id` | funnel, compare | ID книги (default: `AT_WORK_ID`) |
| `--work-id` | cli, delete_runs | То же (устаревающее имя) |
| `--start`, `--end` | funnel | Период |
| `--start-a`, `--end-a`, `--start-b`, `--end-b` | compare | Два периода |
| `--base-order` | funnel, compare | `chapter_order` базы для 100% |
| `--skip-book-page` | funnel, compare | Исключить «Страница книги» |
| `--csv` / `-o` | funnel, compare | Экспорт CSV |
| `--json` | funnel | Источник из файла |
| `--json-a`, `--json-b` | compare | Два файла |

## Семантика метрик воронки

**Суммарная воронка** (`report_funnel.py`):

- `Просмотры` = SUM(views) за весь период по главе
- `% от базы` = просмотры_главы / просмотры_базы × 100 (суммы за период)
- `% от пред.` = отношение к **предыдущей главе в воронке** (суммы)
- `Падение` = разница суммарных просмотров с предыдущим шагом

**Сравнение периодов** (`report_funnel_compare.py`):

- Для каждого **дня**: %_день = views_главы_день / views_базы_день × 100
- μ, σ — по набору дневных % за период
- p-value — Welch t-test между дневными % периода A и B **для одной главы**

## Переменные окружения (минимум)

См. `.env.example`. Критичные для рефакторинга:

- `AT_WORK_ID` → `book_id`
- `MSSQL_*` — подключение к БД
