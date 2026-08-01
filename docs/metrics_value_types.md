# Метрики beyond hit: time и avgTime

Сейчас пайплайн одномерный: URL `valueType=hit` → одна матрица чисел → `chapter_reads.metric_value` → аналитика считает всё как просмотры. У `fetch_runs` ещё нет типа метрики.

На сайте author.today в отчёте статистики есть как минимум:

| `valueType` | Смысл | Типичная агрегация |
|-------------|--------|-------------------|
| `hit` | просмотры | SUM |
| `time` | время чтения | SUM |
| `avgTime` | среднее время чтения | **не SUM** (AVG / отдельные отчёты) |

Ниже — рекомендуемая архитектура с учётом того, что **уже много данных загружено как hit**.

---

## Сделано

- Колонка `chapter_reads.views` переименована в **`metric_value`** (миграция `sp_rename` в `schema.sql`).
- Тип **`DECIMAL(12, 2)`** — запас по величине и две цифры после запятой для avgTime.
- JSON-снимок по-прежнему использует поле `views` (устаревший контракт); в БД пишется `metric_value`.

---

## Почему нельзя «просто сменить valueType»

1. Писать `time`/`avgTime` в ту же колонку без метки на run — смешает метрики в `SUM` и сломает воронку/сравнение/тренд.
2. Три колонки (`metric_value` / `time` / `avg_time`) в одной строке при трёх отдельных загрузках без merge дадут полупустые строки и сложный upsert.
3. Сайт отдаёт **одну** серию за один запрос URL — один Selenium-проход ≠ три метрики сразу.

---

## Рекомендация: один run = одна метрика

**Не расширять строку `chapter_reads` колонками time/avg_time.**  
Хранить тип на уровне загрузки; значение — в `metric_value`.

### Схема БД

1. На `dbo.fetch_runs` добавить `value_type NVARCHAR(16) NOT NULL`.
2. Миграция (идемпотентно, в духе `schema.sql`):
   - `ADD value_type … NULL`
   - `UPDATE dbo.fetch_runs SET value_type = N'hit' WHERE value_type IS NULL`
   - `ALTER … NOT NULL`
   - CHECK / ограничение на набор: `hit` | `time` | `avgTime`
3. ~~`chapter_reads.views`~~ → **`metric_value`** ✅; тип **`DECIMAL(12,2)`** ✅ (hit, секунды time, avgTime с сотыми).
4. Для `avgTime` при загрузке с сайта понадобится парсер с дробями (сейчас DOM — `_parse_int`).

История не ломается: все старые run'ы после backfill = `hit`; `load_snapshot` по умолчанию фильтрует `value_type = 'hit'`.

### Загрузка

- Один Selenium-проход = один `value_type` (уже есть задел: `Settings.value_type` / `AT_VALUE_TYPE` / `build_stats_url`).
- **Догрузка `time`/`avgTime` за прошлые месяцы — отдельные `fetch_runs`**, hit не перекачивать.
- Опционально в UI/CLI: «Загрузить метрики: hit + time + avgTime» = 3 прохода подряд, 3 run'а за тот же период (удобно, в ~3 раза дольше).
- Покрытие / gaps / delete_runs — **по метрике**: «есть hit за июль» ≠ «есть time за июль».

### Чтение и аналитика

```text
load_snapshot(..., metric="hit")  # default
  → JOIN/WHERE fr.value_type = @metric
  → SUM(metric_value) как сейчас (для hit и time)
```

| Метрика | Агрегация по дням/run | Воронка «% от базы» |
|---------|----------------------|---------------------|
| `hit` | SUM | ок (текущее поведение) |
| `time` | SUM (суммарное время) | осмысленно |
| `avgTime` | не SUM по дням/run'ам; AVG дневных или отдельный отчёт | иначе искажение |

Дубли run'ов одной метрики по-прежнему суммируются (известная проблема `delete_runs`); для `avgTime` это ещё опаснее — фильтр по `value_type` обязателен.

### Парсер

- Сейчас DOM-путь — `_parse_int`; для `avgTime`/`time` нужны числа с дробной частью (JS `Number` уже ближе).
- В `StatsTable` / `ReadSnapshot` достаточно одной матрицы значений на снимок; тип метрики — на снимке/run, не в каждой ячейке.

### UI / отчёты

- Селектор метрики в загрузке и (позже) в воронке/сравнении/тренде; default = `hit`.
- Подписи «Просмотры» → контекстные («Время», «Среднее время») по выбранной метрике.
- Не переписывать все отчёты в первом шаге: сначала хранение + загрузка + gaps по метрике.

---

## Чего избегать

- Разные `valueType` в одну колонку без `fetch_runs.value_type`.
- Wide-row (`metric_value` + `time` + `avg_time`) как основной дизайн при раздельных загрузках.
- Считать воронку по `avgTime` через тот же `SUM`, что для hit.
- Перекачивать весь hit-архив ради появления новых метрик.

---

## Порядок внедрения

1. ~~Переименовать `views` → `metric_value`~~ ✅  
2. ~~`metric_value DECIMAL(12,2)`~~ ✅  
3. Миграция `fetch_runs.value_type` + backfill `'hit'`.  
4. `save_snapshot` / `load_snapshot` / gaps / delete учитывают метрику; default `hit`.  
5. Загрузка: явный выбор `hit` | `time` | `avgTime` (+ опция «все три»).  
6. UI отчётов: селектор метрики, default `hit`.  
7. Отдельная семантика analyze для `avgTime` (AVG / свои отчёты).

---

## Связь с кодом

| Слой | Файлы / точки |
|------|----------------|
| URL | `fetch/stats_url.py`, `Settings.value_type`, `AT_VALUE_TYPE` |
| Парсинг | `parse/kendo_grid.py` |
| Домен | `domain/models.py` (`ReadSnapshot.values`) |
| Схема / repo | `storage/mssql/schema.sql`, `storage/mssql_repo.py` |
| Синк | `pipeline/sync_reads.py`, `services/fetch.py` |
| Отчёты | `analyze/*`, `services/reports.py` — пока только hit-семантика |
| Контракты | `docs/data_contracts.md` |

После внедрения `value_type` — ADR в `docs/decisions.md`.
