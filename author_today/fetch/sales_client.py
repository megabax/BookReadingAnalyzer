"""HTTP-клиент строк продаж: cookies Selenium → /merchant/getdetailstable."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any

import requests
from selenium.webdriver.remote.webdriver import WebDriver

from author_today.domain.sales import ITEM_TYPE_WORK, SaleEvent
from author_today.errors import AuthorTodayError
from author_today.fetch.sales_url import DETAILS_BASE, build_details_query

_ASPNET_DATE_RE = re.compile(r"/Date\((-?\d+)(?:[+-]\d{4})?\)/")


class SalesFetchError(AuthorTodayError):
    """Ошибка загрузки / разбора ответа getdetailstable."""


def session_from_driver(driver: WebDriver) -> requests.Session:
    """Перенести cookies браузера в requests.Session."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": driver.execute_script("return navigator.userAgent;")
            or "Mozilla/5.0",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://author.today/merchant/dashboard",
        }
    )
    for cookie in driver.get_cookies():
        session.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie.get("domain") or "author.today",
            path=cookie.get("path") or "/",
        )
    return session


def parse_aspnet_datetime(value: Any) -> datetime:
    """Разобрать ProcessedTime: /Date(ms)/, ISO или datetime."""
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    if value is None:
        raise SalesFetchError("Пустое ProcessedTime в строке продажи.")
    text = str(value).strip()
    match = _ASPNET_DATE_RE.search(text)
    if match:
        ms = int(match.group(1))
        return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).replace(tzinfo=None)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise SalesFetchError(f"Не удалось разобрать дату продажи: {value!r}") from exc
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _coerce_float(value: Any, *, field: str) -> float:
    if value is None:
        raise SalesFetchError(f"Пустое поле {field} в строке продажи.")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise SalesFetchError(f"Некорректное {field}={value!r}") from exc


def parse_sale_event_row(row: dict[str, Any], *, expected_book_id: int) -> SaleEvent | None:
    """
    Строка Data[] → SaleEvent.
    Только ItemType=1 (продажа книги); награды отбрасываем.
    ItemId должен совпадать с фильтром книги.
    """
    item_type = row.get("ItemType")
    try:
        item_type_int = int(item_type) if item_type is not None else None
    except (TypeError, ValueError):
        return None
    if item_type_int != ITEM_TYPE_WORK:
        return None

    item_id_raw = row.get("ItemId")
    try:
        item_id = int(item_id_raw)
    except (TypeError, ValueError) as exc:
        raise SalesFetchError(f"Некорректный ItemId={item_id_raw!r}") from exc
    if item_id != expected_book_id:
        raise SalesFetchError(
            f"ItemId={item_id} не совпадает с book_id={expected_book_id} "
            "(ожидаются только продажи выбранной книги)."
        )

    work_format_raw = row.get("WorkFormat")
    work_format: int | None
    if work_format_raw is None or work_format_raw == "":
        work_format = None
    else:
        try:
            work_format = int(work_format_raw)
        except (TypeError, ValueError) as exc:
            raise SalesFetchError(f"Некорректный WorkFormat={work_format_raw!r}") from exc

    return SaleEvent(
        processed_at=parse_aspnet_datetime(row.get("ProcessedTime")),
        book_id=item_id,
        work_format=work_format,
        price=_coerce_float(row.get("Price"), field="Price"),
        commission=_coerce_float(row.get("Commission"), field="Commission"),
        author_income=_coerce_float(row.get("AuthorIncome"), field="AuthorIncome"),
    )


def _request_details_page(
    session: requests.Session,
    params: dict[str, str | int],
) -> dict[str, Any]:
    """Запрос одной страницы getdetailstable (POST, fallback GET)."""
    response = session.post(DETAILS_BASE, data=params, timeout=90)
    if response.status_code >= 400 or "json" not in (response.headers.get("Content-Type") or "").lower():
        # Иногда сайт отдаёт JSON только на GET с query.
        response = session.get(DETAILS_BASE, params=params, timeout=90)
    if response.status_code == 401 or response.status_code == 403:
        raise SalesFetchError(
            f"Нет доступа к отчёту продаж (HTTP {response.status_code}). "
            "Нужен коммерческий статус и вход в ЛК."
        )
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as exc:
        raise SalesFetchError(
            "Ответ getdetailstable не JSON (возможна страница входа)."
        ) from exc
    if not isinstance(payload, dict):
        raise SalesFetchError(f"Неожиданный JSON getdetailstable: {type(payload)}")
    errors = payload.get("Errors")
    if errors:
        raise SalesFetchError(f"Ошибки getdetailstable: {errors}")
    return payload


def fetch_sale_events(
    session: requests.Session,
    book_id: int,
    period_start: date,
    period_end: date,
    *,
    page_size: int = 200,
) -> list[SaleEvent]:
    """Все продажи книги за период (пагинация pageSize до 200)."""
    if page_size < 1 or page_size > 200:
        raise ValueError("page_size должен быть в диапазоне 1..200")

    events: list[SaleEvent] = []
    page = 1
    total: int | None = None

    while True:
        params = build_details_query(
            book_id,
            period_start,
            period_end,
            page=page,
            page_size=page_size,
        )
        payload = _request_details_page(session, params)
        rows = payload.get("Data") or []
        if not isinstance(rows, list):
            raise SalesFetchError("Поле Data в ответе getdetailstable не список.")

        if total is None:
            try:
                total = int(payload.get("Total") or 0)
            except (TypeError, ValueError):
                total = len(rows)

        for row in rows:
            if not isinstance(row, dict):
                continue
            event = parse_sale_event_row(row, expected_book_id=book_id)
            if event is not None:
                events.append(event)

        # Total на сайте включает награды; после фильтра событий может быть меньше.
        fetched_raw = (page - 1) * page_size + len(rows)
        if not rows or fetched_raw >= total or len(rows) < page_size:
            break
        page += 1
        if page > 10_000:
            raise SalesFetchError("Слишком много страниц getdetailstable — останов.")

    return events
