# Веб-интерфейс на Streamlit

Рекомендации по UI для AutorToday: выбор технологии, архитектура, этапы, связь с рефакторингом.

---

## Решение

**Streamlit** — основной UI (не Django, не PyQt на первом этапе).

| Критерий | Почему Streamlit |
|----------|------------------|
| Задача | Таблицы, фильтры, графики по воронке — типичный кейс |
| Аудитория | Один автор, локальный запуск на Windows |
| Стек | Уже есть pandas, отчёты, CSV |
| Скорость | MVP за 1–2 сессии без отдельного фронтенда |
| Рефакторинг | UI импортирует `author_today`, не дублирует `scripts/` |

**Django** — избыточен (ORM, admin, auth). Конфликтует с текущим pyodbc + ручным SQL.

**PyQt** — имеет смысл только если нужен desktop без браузера; больше кода на таблицы и графики.

**FastAPI** — опционально позже, если понадобится отдельный HTTP API; Streamlit может остаться клиентом.

---

## Установка

```bat
cd D:\Pythons\AutorToday
venv\Scripts\activate.bat
pip install -r requirements.txt -r requirements-ui.txt
streamlit run streamlit_app.py
```

Откроется браузер (по умолчанию `http://localhost:8501`).

Файлы:

| Путь | Назначение |
|------|------------|
| `requirements-ui.txt` | Зависимость `streamlit` |
| `streamlit_app.py` | Точка входа |
| `.streamlit/config.toml` | Тема и настройки сервера |
| `author_today/services/reports.py` | Сервисный слой для отчётов (без UI-логики) |

---

## Архитектура UI

```
streamlit_app.py          ← страницы, виджеты, кэш st.cache_data
        │
        ▼
author_today/services/    ← оркестрация (reports.py)
        │
        ▼
author_today/analyze/     ← funnel, funnel_compare
author_today/storage/     ← mssql_repo (после рефакторинга §2)
author_today/domain/      ← ReadSnapshot (после §3)
```

### Правила

1. **Не вызывать** `subprocess` / `os.system("python scripts/...")` из UI.
2. **Не писать SQL** в `streamlit_app.py` — только через repository / services.
3. **Настройки** — `Settings.from_env()`; секреты только в `.env`, не в `st.session_state`.
4. **Долгие операции** (Selenium) — не в синхронной кнопке; отдельный этап (фон, subprocess с логом, или CLI).

---

## План экранов (MVP → полный)

### Этап A — отчёты по уже загруженным данным (первый рабочий UI)

| Экран | Функции |
|-------|---------|
| **Воронка** | book_id, период, base-order, skip-book-page; таблица + line/bar chart по % от базы |
| **Сравнение** | период A / B, base-order; таблица μ, σ, p-value; подсветка p &lt; 0,05 |

Источник: **только MS SQL** (ADR-012). JSON в `data/raw/` не показываем в UI.

### Этап B — удобство

- Скачать CSV из UI (`save_funnel_csv` / `save_funnel_compare_csv`)
- Выбор книги из `config/books.yaml` (когда файл подключат в settings)
- `st.cache_data` на тяжёлые запросы к БД

### Этап C — загрузка с сайта (позже)

- Кнопка «Загрузить период» → фоновый процесс / отдельное окно терминала
- Поле кода нового устройства (как в CLI)
- Статус: running / done / error; данные в MS SQL

### Не в MVP

- Мультипользовательский доступ, регистрация
- Редактирование данных в БД (кроме будущей кнопки «удалить run» с подтверждением)
- Продажи из `reclan.csv` (отдельный модуль `analyze/sales.py`)

---

## Визуальные элементы (рекомендации)

### Воронка

- `st.dataframe` — таблица шагов (просмотры, % от базы, % от пред.)
- `st.line_chart` или Plotly — % от базы по `chapter_order` (ось X — номер главы или сокращённое имя)
- Метрики в `st.metric`: первая/последняя глава, % дочитывания

### Сравнение периодов

- Таблица с колонками μ_A, μ_B, Δ, p-value
- Условное форматирование: `p_value < 0.05` — значимое изменение
- Опционально: dual line chart (средние дневные % по двум периодам) — после выгрузки дневных рядов в service

### Sidebar (общий)

- `book_id`
- Период(ы): `st.date_input`
- Чекбоксы: skip book page, base-order

---

## Кэширование и производительность

```python
@st.cache_data(ttl=300)
def cached_funnel(...):
    return load_funnel_steps(...)
```

- TTL 5–10 минут для MSSQL-агрегатов
- `cache_clear` при явном «Обновить»
- Не кэшировать Selenium-сессии

---

## Зависимость от рефакторинга

| Сначала (блокирует качественный UI) | Можно параллельно с UI-скелетом |
|-------------------------------------|----------------------------------|
| §7 сервисный слой / cli_common | Каркас `streamlit_app.py`, tabs |
| Ручной smoke MSSQL на своей книге | `services/reports.py` (готово) |

| Уже сделано | |
|-------------|--|
| §1 book_id | ✅ |
| §2 SQL в `mssql_repo` | ✅ |
| §3 MSSQL → ReadSnapshot | ✅ |
| §4 тесты | ✅ (unit + smoke) |
| §0 docs | ✅ |
| JSON скрыт (ADR-012) | ✅ |

**Порядок:** подключить отчёты в Streamlit (этап A) → §7 → этап B → Selenium в UI (этап C).

---

## Структура файлов (целевая)

```
streamlit_app.py
author_today/
  services/
    reports.py          # есть
    fetch.py            # позже: обёртка sync_reads для фона
  ui/
    components.py       # позже: общие виджеты sidebar
    pages/              # опционально: multipage st.navigation
docs/ui_streamlit.md    # этот файл
```

Пока один файл `streamlit_app.py` достаточен; при росте — вынести страницы в `author_today/ui/`.

---

## Риски

| Риск | Митигация |
|------|-----------|
| Дублирование логики CLI | Только `services/*` |
| Зависание UI на Selenium | Этап C отдельно, фон |
| Кодировка / кириллица в Windows | UTF-8 в терминале; Streamlit в браузере обычно ок |
| Дубли в БД искажают графики | Подсказка в UI + ссылка на `delete_runs.py` |

---

## Связанные документы

- [decisions.md](decisions.md) — ADR-011 Streamlit
- [refactoring_plan.md](../refactoring_plan.md) — §18 UI
- [architecture_baseline.md](architecture_baseline.md) — текущие потоки данных
- [pre_refactor_checklist.md](pre_refactor_checklist.md) — фаза UI
