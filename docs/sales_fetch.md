# Загрузка продаж с merchant/dashboard

**Статус:** дизайн зафиксирован; код **не** реализован (ждёт отдельного согласования).

**Пример URL:**  
`https://author.today/merchant/dashboard?groupBy=work&startDate=2026-10-13T20%3A00%3A00.000Z&endDate=2026-10-20T19%3A59%3A59.999Z&itemId=172953`  

Описание ниже снято с живой страницы ЛК (Kendo Grid + `app.init("merchantDashboard", …)`). Локальные HTML-снимки в репозиторий не кладём.

Связанные пункты: [`new_features.md`](../new_features.md) §15, черновик таблиц в [`data_contracts.md`](data_contracts.md).

---

## Почему не PDF и не публичное API

| Источник | Проблема |
|----------|----------|
| PDF «отчёт агента» | Есть названия книг, **нет** `workId`. Название на сайте / в PDF может не совпадать с `dbo.books.title` → матчинг хрупкий. |
| `reclan.csv` (legacy) | Внешняя выгрузка без гарантированного id; модуль `analyze/sales.py` удалён. |
| [api.author.today](https://api.author.today/help) | Нет эндпоинтов статистики продаж (как и прочтений по главам). |

**Источник правды:** личный кабинет коммерческого автора — страница «Сводка» / «Сводный отчет о продажах» (`/merchant/dashboard`).

---

## URL и фильтры страницы

База: `https://author.today/merchant/dashboard`

| Query | Значения | v1 |
|-------|----------|-----|
| `groupBy` | `work` \| `series` \| `format` | только **`work`** |
| `startDate`, `endDate` | ISO UTC, как у stats: начало дня `…T20:00:00.000Z`, конец `…T19:59:59.999Z` | да |
| `itemId` | id произведения (= наш `book_id` / `workId`) | да |

На странице Knockout + `app.init("merchantDashboard", { works, series, workFormat, startDate, endDate, … })`.  
В init уже есть `works[]`: `{ id, title }` — позже можно синхронизировать названия в `dbo.books`.

Меню ЛК: «Коммерческий статус» → «Сводка» (`/merchant/dashboard`). Рядом: скидки, вывод средств, агентский договор.

---

## Откуда брать строки (не DOM)

Грид `#grid` — **Kendo UI** с транспортом `aspnetmvc-ajax`. Данные **не** лежат в сохранённом HTML (в примере tbody пустой: «Нет записей») — подгружаются AJAX после init.

| | |
|--|--|
| Read URL | **`/merchant/getdetailstable`** |
| Фильтр | те же `groupBy`, даты, `itemId` (через `app.viewModel.getFilterData`) |
| Ответ | `{ Data, Total, Errors }` |
| Пагинация | server-side; в UI pageSizes `20, 50, 100, 200` |
| Сортировка по умолчанию | `ProcessedTime` desc |

**Рекомендуемый способ загрузки (будущий код):** Selenium-login (как для прочтений) → cookies сессии → HTTP к `getdetailstable` с `pageSize=200`, цикл страниц до `Total`. Не парсить DOM грида.

Инфоблоки (книг / наград / доход / баланс) и AmCharts (`#chartdiv`) в **v1 storage не сохраняем**.

---

## Поля строки `Data[]`

Из schema Kendo в HTML-эталоне:

| Поле | Тип (сайт) | Смысл |
|------|------------|--------|
| `ItemId` | number | Id предмета: при продаже книги = **workId** → связь с `books.id` |
| `ItemType` | number | `1` = продажа произведения; иначе награда (иконка gift в шаблоне) |
| `WorkFormat` | number | `1` ebook, `2` audiobook |
| `ProcessedTime` | date | Время операции (на графике сутки по MSK, UTC+3) |
| `ItemTitle` | string | Наименование |
| `ItemDescription` | string | Описание (опционально) |
| `Price` | number | Цена |
| `Commission` | number | Комиссия (в гриде как процент) |
| `AuthorIncome` | number | Доход автора |
| `Discount` | number \| null | Скидка |
| `CoAuthorsCount` | number | Соавторы (деление дохода) |
| `UserId` / `UserName` / `UserFIO` | | Читатель |
| `AccountId` / `AccountFIO` | | Аккаунт (для объединённых аккаунтов; колонка скрыта) |
| `AuthorId`, `CoAuthorId`, `SecondCoAuthorId` | | Авторы |

Минимум для v1 persist: `ProcessedTime`, `ItemId`, `ItemType`, `WorkFormat`, `ItemTitle`, `Price`, `Commission`, `AuthorIncome`.

---

## Поток (целевой)

```text
Selenium auth  →  (опц.) /merchant/dashboard
               →  GET/POST /merchant/getdetailstable (пагинация)
               →  sale_runs + sale_events (MS SQL)
```

Переиспользовать [`author_today/auth/`](../author_today/auth/). Не смешивать с `fetch_runs` / `chapter_reads`.

---

## Черновик схемы MS SQL

### `dbo.sale_runs`

Снимок одной загрузки (аналог `fetch_runs`):

| Колонка | Тип | Описание |
|---------|-----|----------|
| `id` | BIGINT IDENTITY PK | |
| `work_id` | INT FK → books.id | Книга фильтра (`itemId`) |
| `period_start`, `period_end` | DATE | |
| `fetched_at` | DATETIME2 | |

### `dbo.sale_events`

Строки ответа `Data[]`:

| Колонка | Тип | Описание |
|---------|-----|----------|
| `id` | BIGINT IDENTITY PK | Явного sale-id в schema сайта нет |
| `run_id` | BIGINT FK → sale_runs ON DELETE CASCADE | |
| `processed_at` | DATETIME2 | `ProcessedTime` |
| `item_id` | INT | `ItemId` |
| `item_type` | TINYINT | `ItemType` |
| `work_format` | TINYINT NULL | `WorkFormat` |
| `item_title` | NVARCHAR(500) | |
| `price` | DECIMAL(12,2) | |
| `commission` | DECIMAL(12,4) | доля / как придёт с сайта |
| `author_income` | DECIMAL(12,2) | |
| опционально | | `discount`, `coauthors_count`, `reader_user_id` |

При `item_type = 1` логическая связь `item_id` → `books.id`. Награды (`item_type ≠ 1`) FK на книгу не требовать (уточнить на живом JSON).

**Дубли загрузок:** защита по пересечению периода × `work_id` для `sale_runs` (по аналогии с §14 для `fetch_runs`).

Полный контракт после реализации — в [`data_contracts.md`](data_contracts.md) (сейчас черновик «запланировано»).

---

## Границы v1 / не делать

**v1 (когда согласуем код):** одна книга (`itemId`), `groupBy=work`, события в `sale_events`, CLI/UI флаг отдельно от прочтений.

**Не в v1:**

- импорт `reclan.csv` / парсинг PDF агента;
- только месячные агрегаты без сырых событий;
- сохранение графика AmCharts и карточек баланса;
- `groupBy=series|format` как основной режим.

---

## Реализация позже (чеклист кода)

- [ ] `author_today/fetch/sales_url.py` — сбор URL dashboard / параметров
- [ ] клиент `getdetailstable` + пагинация; сохранить фикстуру JSON из DevTools
- [ ] domain-модель + `persist` / schema migration
- [ ] UI «Загрузка» / CLI — режим «продажи»
- [ ] unit-тесты на парсер ответа
- [ ] обновить этот документ: статус → реализовано; уточнить метод HTTP и формат дат в JSON
