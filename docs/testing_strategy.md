# Стратегия тестирования перед и во время рефакторинга

Цель: зафиксировать поведение до изменений и ловить регрессии при переносе кода.

## Инструменты

```bat
pip install pytest
```

Структура (создать при старте фазы 1):

```
tests/
  conftest.py              # фикстуры, пути к fixtures
  fixtures/
    snapshot_minimal.json  # минимальный валидный снимок
    snapshot_july.json     # опционально: реальный анонимизированный файл
  unit/
    test_funnel.py
    test_funnel_compare.py
    test_stats.py
    test_periods.py
    test_read_snapshot.py
```

Запуск:

```bat
pytest
pytest tests/unit/test_funnel.py -v
```

## Приоритет 1 — до любого рефакторинга analyze/domain

### `test_funnel.py`

| Тест | Что проверяет |
|------|----------------|
| `build_funnel_basic` | порядок шагов, % от первой |
| `build_funnel_skip_book_page` | нет «Страница книги», step_num 1..N |
| `build_funnel_base_order` | 100% у главы с `base-order` |
| `build_funnel_missing_base` | `ValueError` с списком order |

### `test_funnel_compare.py`

| Тест | Что проверяет |
|------|----------------|
| `daily_pct_constant` | μ = ожидаемый % при стабильных днях |
| `compare_two_periods` | μ_A ≠ μ_B, p-value < 0.05 на синтетике |
| `insufficient_days` | p-value = None при n < 2 |
| `skip_zero_baseline_days` | дни с baseline_views=0 не в n |

### `test_stats.py`

| Тест | Что проверяет |
|------|----------------|
| `mean_and_sigma` | известные числа |
| `welch_identical` | p ≈ 1 |
| `welch_different` | p < 0.05 |
| `welch_zero_variance` | краевые случаи |
| `welch_scipy_parity` | skip если нет scipy; иначе \|p_scipy - p_fallback\| < 0.01 |

### `test_periods.py`

| Тест | Что проверяет |
|------|----------------|
| `single_month` | один chunk |
| `cross_month` | несколько chunks, границы месяцев |
| `needs_monthly_chunks` | true/false на границах |

### `test_read_snapshot.py`

| Тест | Что проверяет |
|------|----------------|
| `from_stats_table_same_year` | парсинг DD.MM |
| `from_stats_table_cross_year` | **ожидаем fail сейчас** → станет pass после фикса |
| `to_document_roundtrip` | поля JSON после serialize |
| `from_json` | после реализации ADR-002 |

## Приоритет 2 — после переноса SQL в repo

- Интеграционные тесты с **mock cursor** или тестовой БД (опционально, если есть SQL Express в CI)
- Проверка SQL-методов: `aggregate_chapter_views`, `daily_chapter_matrix`, `delete_runs_by_fetched_at`

## Приоритет 3 — smoke / golden

| Тест | Описание |
|------|----------|
| `golden_funnel_csv` | fixture JSON → `save_funnel_csv` → сравнение с эталонным CSV (нормализовать переводы строк) |
| `cli_help` | `report_funnel.py --help` exit 0 |

## Что не тестировать на первом этапе

- Selenium / реальный сайт (слишком хрупко)
- Полный pyodbc без тестовой БД
- legacy/

## Критерий готовности к рефакторингу фазы 2+

- [ ] pytest зелёный на приоритете 1
- [ ] `test_read_snapshot_cross_year` помечен `xfail` с ссылкой на known_issues §1 до фикса
- [ ] Зафиксирован минимальный `tests/fixtures/snapshot_minimal.json`

## Минимальная фикстура JSON

```json
{
  "book_id": 1,
  "period_start": "2025-07-01",
  "period_end": "2025-07-02",
  "fetched_at": "2026-01-01T12:00:00",
  "dates": [
    {
      "date": "2025-07-01",
      "chapters": [
        { "chapter": "Страница книги", "views": 100 },
        { "chapter": "Глава 1", "views": 80 },
        { "chapter": "Глава 2", "views": 40 }
      ]
    },
    {
      "date": "2025-07-02",
      "chapters": [
        { "chapter": "Страница книги", "views": 50 },
        { "chapter": "Глава 1", "views": 50 },
        { "chapter": "Глава 2", "views": 25 }
      ]
    }
  ]
}
```

При `base-order=2` («Глава 1»): день1 глава2 = 50%, день2 глава2 = 50% → μ=50, σ=0.
