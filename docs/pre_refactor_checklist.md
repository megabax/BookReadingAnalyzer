# Чеклист перед рефакторингом

Использовать **перед началом каждой фазы** из [`refactoring_plan.md`](../refactoring_plan.md).

## Общий чеклист (один раз)

- [ ] Прочитаны: glossary, architecture_baseline, data_contracts, known_issues, decisions
- [ ] Текущая ветка закоммичена или создана ветка `refactor/<фаза>`
- [ ] Есть рабочий `.env` / доступ к MSSQL (для smoke вручную)
- [ ] Зафиксирован эталонный прогон отчётов на своей книге (скрин или CSV в `data/reports/`, не в git)

## Фаза 0: Подготовка тестов

- [x] `pip install pytest` (`requirements-dev.txt`)
- [x] Создана структура `tests/` по `testing_strategy.md`
- [x] Добавлен `tests/fixtures/snapshot_minimal.json`
- [x] Unit-тесты на funnel, compare, stats, periods — зелёные
- [x] Cross-year тест green

**Критерий выхода:** `pytest` проходит; можно менять analyze с уверенностью.

---

## Фаза 1: ReadSnapshot + MSSQL → snapshot

- [x] Прочитан ADR-002, ADR-005 (если трогаете sync)
- [x] Добавлен `ReadSnapshot.from_json(path)`
- [x] `funnel_from_json` / `daily_matrix_from_json` используют snapshot
- [x] Исправлен cross-year в `from_stats_table` + тест green
- [x] Ручной smoke: воронка и compare из MSSQL согласованы с доменной моделью

**Критерий выхода:** загрузка снимка из MSSQL в `ReadSnapshot`; cross-year тест green.

---

## Фаза 2: SQL в mssql_repo

- [x] Прочитан ADR-003
- [x] Методы repo реализованы и покрыты (unit mock)
- [x] `funnel.py`, `funnel_compare.py`, `delete_runs.py` без прямого SQL
- [ ] `delete_runs.py --dry-run` на реальной БД — те же счётчики, что до переноса

**Критерий выхода:** grep по `SELECT` в `analyze/` и `delete_runs.py` — пусто.

---

## Фаза 3: book_id в CLI

- [x] Прочитан ADR-001
- [x] `--book-id` везде; `--work-id` с предупреждением deprecation
- [x] README и glossary согласованы
- [x] `AT_BOOK_ID` в `.env.example`, `books.yaml` → `book_id`

---

## Фаза 4: cli_common / pyproject.toml

- [ ] Прочитан ADR-008
- [ ] `pip install -e .` работает без `sys.path` hack (хотя бы в новых скриптах)
- [ ] Общие argparse-helpers для funnel-скриптов
- [ ] `--help` всех entry points без ошибок

---

## Фаза 5: Дедуп analyze + cleanup

- [ ] `chapter_filters`, `formatting`, `snapshot_loaders` выделены
- [ ] `stats_test.py` переименован (ADR-006), импорты обновлены
- [ ] Решение по stubs: report.py, sqlite, sales (удалить или оставить с пометкой)
- [ ] `REPORTS_DIR` в settings
- [ ] README «Структура» обновлена

---

## Фаза UI: Streamlit (подготовка)

- [x] `requirements-ui.txt`, `streamlit_app.py`, `.streamlit/config.toml`
- [x] `author_today/services/reports.py`
- [x] `docs/ui_streamlit.md`, ADR-011, §18 в refactoring_plan
- [ ] Этап A: воронка и compare в UI (после §2–§3)
- [ ] Этап C: загрузка Selenium из UI

---

## После каждого merge

- [ ] `pytest`
- [ ] Ручной smoke (минимум 2 пункта из known_issues §регрессионные сценарии)
- [x] `refactoring_plan.md` — отметить выполненные пункты (п. 1 ✅)
- [ ] Новые ADR в `decisions.md` при изменении контрактов

## Откат

- Каждая фаза — отдельный коммит или PR
- При регрессии: revert коммита фазы, не «чинить на ходу» без теста
