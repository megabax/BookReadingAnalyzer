# Загрузка продаж с merchant/dashboard

**Статус:** реализовано (v1).

**Пример URL:**  
`https://author.today/merchant/dashboard?groupBy=work&startDate=2026-10-13T20%3A00%3A00.000Z&endDate=2026-10-20T19%3A59%3A59.999Z&itemId=172953`

Связанные пункты: [`new_features.md`](../new_features.md) §15, контракт в [`data_contracts.md`](data_contracts.md).

---

## Почему не PDF и не публичное API

| Источник | Проблема |
|----------|----------|
| PDF «отчёт агента» | Есть названия книг, **нет** `workId`. |
| `reclan.csv` (legacy) | Без гарантированного id. |
| [api.author.today](https://api.author.today/help) | Нет эндпоинтов продаж. |

**Источник:** ЛК → `/merchant/dashboard` → AJAX **`/merchant/getdetailstable`**.

---

## Как работает код

1. Selenium: открыть dashboard URL, `auth.ensure_logged_in`.
2. Cookies → `requests.Session`.
3. Пагинация `getdetailstable` (`pageSize=200`, POST с fallback GET).
4. Берутся только строки **`ItemType == 1`** (продажа книги); награды отбрасываются.
5. `ItemId` должен совпадать с выбранным `book_id` (FK на `dbo.books`).
6. Persist: `sale_runs` + `sale_events` (без названий предмета, без соавторов).

Модули:

| Файл | Роль |
|------|------|
| `fetch/sales_url.py` | URL dashboard / параметры details |
| `fetch/sales_client.py` | HTTP + парсинг строк |
| `fetch/sales_page.py` | auth + загрузка |
| `pipeline/sync_sales.py` | CLI-цикл |
| `services/fetch.py` | `FetchJob(mode="sales")` |
| `scripts/fetch_sales.py` | CLI |

UI «Загрузка»: переключатель «Прочтения» / «Продажи».

---

## Поля события (v1)

| Поле сайта | Колонка БД |
|------------|------------|
| `ProcessedTime` | `processed_at` |
| `ItemId` | `book_id` |
| `WorkFormat` | `work_format` (1 ebook, 2 audio) |
| `Price` | `price` |
| `Commission` | `commission` |
| `AuthorIncome` | `author_income` |

Не сохраняем: `ItemTitle`, соавторов, читателя, награды (`ItemType ≠ 1`).

Даты `ProcessedTime`: ASP.NET `/Date(ms)/` или ISO.

---

## Схема MS SQL

См. `schema.sql` и [`data_contracts.md`](data_contracts.md): `dbo.sale_runs`, `dbo.sale_events`.

Применение: `python scripts/init_mssql.py` или автоматически при `persist_sale_snapshot` / `ensure_schema`.

---

## CLI

```bash
python scripts/fetch_sales.py --book-id 172953 --start 2026-10-01 --end 2026-10-31
python scripts/fetch_sales.py --book-id 172953 --start 2026-10-01 --end 2026-10-31 --raw
```

---

## Не в v1

- импорт `reclan.csv` / PDF агента;
- `groupBy=series|format`;
- AmCharts / карточки баланса;
- защита от дублей sale_runs (§14-аналог);
- UI-отчёты по продажам (только загрузка в БД).
