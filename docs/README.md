# Документация перед рефакторингом

Набор текстов фиксирует **текущее состояние** проекта до изменений из [`refactoring_plan.md`](../refactoring_plan.md).
Используйте их как эталон: после рефакторинга поведение и контракты не должны ломаться без явного решения.

| Документ | Назначение |
|----------|------------|
| [glossary.md](glossary.md) | Термины и соглашения об именах |
| [architecture_baseline.md](architecture_baseline.md) | Текущая архитектура и потоки данных |
| [data_contracts.md](data_contracts.md) | Форматы JSON, БД, CLI, отчётов |
| [known_issues.md](known_issues.md) | Известные баги и ограничения (не исправлять «мимоходом») |
| [decisions.md](decisions.md) | Принятые решения на время рефакторинга (ADR) |
| [testing_strategy.md](testing_strategy.md) | Что и как тестировать до/во время рефакторинга |
| [pre_refactor_checklist.md](pre_refactor_checklist.md) | Чеклист перед каждой фазой |
| [ui_streamlit.md](ui_streamlit.md) | Веб-интерфейс: Streamlit, экраны, установка |

**Порядок чтения:** glossary → architecture_baseline → data_contracts → known_issues → decisions → testing_strategy.
