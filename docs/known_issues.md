# Известные проблемы и ограничения

Зафиксировано **до рефакторинга**. Исправление — по [`refactoring_plan.md`](../refactoring_plan.md), не «случайно» при других задачах.

## Баги

### 1. Даты через границу года

**Файл:** `author_today/domain/models.py` → `ReadSnapshot.from_stats_table`

Всем колонкам `DD.MM` присваивается `period_end.year`. Период декабрь–январь даёт неверный год для декабрьских дней.

**Воспроизведение:** `--start 2025-12-01 --end 2026-01-31`.

---

### 2. CSV/JSON только за последний месяц при длинном периоде

**Файл:** `author_today/pipeline/sync_reads.py` → `sync_reads_by_period`

При `needs_monthly_chunks()` в `-o` / `--json` попадает таблица **последнего** chunk; в `data/raw` и MSSQL сохраняются **все** chunks.

**Воспроизведение:** период > 1 календарного месяца + `-o out.csv`.

---

### 3. Расхождение JSON vs MSSQL в отчётах

**Файлы:** `analyze/funnel.py`, `analyze/funnel_compare.py`

- Из JSON: `chapter_order` = индекс в массиве / порядок первого появления
- Из MSSQL: `chapter_order` из `chapter_reads` (как при сохранении с сайта)

При одном файле JSON и БД результаты воронки должны совпадать только если порядок глав стабилен.

---

## Ограничения модели (не баги, но важно для интерпретации)

### Просмотры ≠ уникальные читатели

Один пользователь может дать просмотры нескольким главам → `% от пред.` может быть **> 100%**.

### Дубли fetch_runs в БД

Повторная загрузка того же периода **добавляет** новый run; аналитика **суммирует** views. Очистка: `scripts/delete_runs.py` по `work_id` + диапазон `fetched_at`.

### p-value при малом числе дней

Меньше 2 дней с ненулевой базой в периоде → p-value = `—`.

### Нулевая дисперсия

Если дневные % константны в обоих периодах, p-value = 1 (одинаково) или 0 (разные средние).

### scipy не в requirements.txt

`stats_test.py` работает без scipy (fallback); при установленном scipy используется `ttest_ind`.

---

## Технический долг (не блокирует работу)

| Проблема | Где |
|----------|-----|
| SQL в analyze и delete_runs, не в repo | см. refactoring_plan §2 |
| `stats_test.py` — имя как у тестов | analyze/ |
| `books.yaml` не читается | config/ |
| `ReadRepository` не используется единообразно | storage/ |
| `scripts/report.py` — placeholder | scripts/ |
| Нет unit-тестов | весь проект |

---

## Регрессионные сценарии для проверки после рефакторинга

1. Загрузка июля 2025, `book_id=323389`, запись в raw + MSSQL
2. `report_funnel.py --skip-book-page --base-order 2 --csv`
3. `report_funnel_compare.py` два месяца, `--base-order 2 --csv`
4. `delete_runs.py --dry-run` по диапазону `fetched_at`
5. Период в 2+ месяца: все chunks в raw, поведение `-o` документировано или исправлено
