"""Парсинг Kendo Grid со страницы статистики author.today."""

from __future__ import annotations

import re
import time

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait

from author_today.domain.models import StatsTable

DATE_RE = re.compile(r"^\d{2}\.\d{2}$")
CHAPTER_MARKERS = ("глава", "интерлюдия", "страница книги", "вместо эпилога", "часть")
SCROLL_SETTLE_S = 0.2
MAX_SCROLL_PASSES = 40


def _cell_texts(row) -> list[str]:
    cells = row.find_elements(By.CSS_SELECTOR, "td, th")
    if not cells:
        cells = row.find_elements(By.CSS_SELECTOR, "[role='gridcell']")
    return [c.text.strip() for c in cells]


def _parse_int(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    try:
        return int(value.replace("\xa0", "").replace(" ", ""))
    except ValueError:
        return None


def _is_date_header(text: str) -> bool:
    return bool(DATE_RE.match(text.strip()))


def _is_chapter_label(text: str) -> bool:
    low = text.strip().lower()
    if not low or low == "часть":
        return False
    return any(m in low for m in CHAPTER_MARKERS)


def _score_grid_element(element) -> int:
    text = element.text
    if not text:
        return 0
    score = 0
    if "Часть" in text:
        score += 5
    score += min(len(DATE_RE.findall(text)), 31) * 2
    if re.search(r"Глава\s+\d+", text, re.I):
        score += 10
    if "Страница книги" in text:
        score += 5
    if re.search(r"\b\d{1,3}\b", text):
        score += 3
    return score


def find_best_grid(driver: WebDriver, timeout: int):
    wait = WebDriverWait(driver, timeout)

    def any_grid_present(drv):
        for sel in (".k-grid", "div.k-grid-content-locked", "table[role='grid']", "table.table"):
            if drv.find_elements(By.CSS_SELECTOR, sel):
                return True
        return False

    wait.until(any_grid_present)

    candidates = list(driver.find_elements(By.CSS_SELECTOR, ".k-grid"))
    if not candidates:
        for el in driver.find_elements(By.CSS_SELECTOR, "table"):
            if "Часть" in el.text or DATE_RE.search(el.text):
                candidates.append(el)

    if not candidates:
        raise TimeoutException("Таблица статистики не найдена на странице")

    return max(candidates, key=_score_grid_element)


def _header_scroll_el(grid):
    wraps = grid.find_elements(By.CSS_SELECTOR, ".k-grid-header-wrap.k-auto-scrollable")
    return wraps[0] if wraps else None


def _visible_header_dates(grid) -> list[str]:
    header = _header_scroll_el(grid)
    source = header if header is not None else grid
    dates: list[str] = []
    for th in source.find_elements(By.CSS_SELECTOR, "th"):
        t = th.text.strip()
        if _is_date_header(t):
            dates.append(t)
    return dates


def iter_scroll_row_indices(locked_labels: list[str]) -> list[tuple[str, int]]:
    """
    Индексы строк прокручиваемой части для подписей из locked-колонки.

    Строка «Часть» есть только слева; при zip() она сдвигает значения на одну главу.
    """
    pairs: list[tuple[str, int]] = []
    scroll_idx = 0
    for label in locked_labels:
        if not label or label == "Часть":
            continue
        if not _is_chapter_label(label) and label != "Страница книги":
            continue
        pairs.append((label, scroll_idx))
        scroll_idx += 1
    return pairs


def _values_for_date_indices(
    s_cells: list[str],
    date_indices: list[int],
) -> list[int | None]:
    parsed = [_parse_int(v) for v in s_cells]
    return [parsed[i] if 0 <= i < len(parsed) else None for i in date_indices]


_VISIBLE_DATE_SLICE_JS = """
const headerEl = arguments[0];
const scrollEl = arguments[1];
if (!headerEl || !scrollEl) return {dates: [], indices: []};
const viewRect = scrollEl.getBoundingClientRect();
const dates = [];
const indices = [];
let dateIdx = 0;
for (const th of headerEl.querySelectorAll('th')) {
    const text = (th.textContent || '').trim();
    if (!/^\\d{2}\\.\\d{2}$/.test(text)) continue;
    const r = th.getBoundingClientRect();
    if (r.right > viewRect.left + 1 && r.left < viewRect.right - 1) {
        dates.push(text);
        indices.push(dateIdx);
    }
    dateIdx += 1;
}
return {dates, indices};
"""


def _visible_viewport_date_slice(
    driver: WebDriver,
    header,
    scroll,
) -> tuple[list[str], list[int]]:
    """Даты и индексы колонок, видимые в окне горизонтальной прокрутки."""
    if header is None:
        return [], []
    payload = driver.execute_script(_VISIBLE_DATE_SLICE_JS, header, scroll)
    if not payload:
        return [], []
    dates = [str(d) for d in payload.get("dates", [])]
    indices = [int(i) for i in payload.get("indices", [])]
    return dates, indices


def merge_scroll_slice(
    date_order: list[str],
    chapter_values: dict[str, dict[str, int | None]],
    *,
    chapter: str,
    dates_batch: list[str],
    values: list[int | None],
) -> None:
    """Добавить видимый фрагмент таблицы (для тестов и прокрутки)."""
    if chapter not in chapter_values:
        chapter_values[chapter] = {}
    for day in dates_batch:
        if day not in date_order:
            date_order.append(day)
    for day, value in zip(dates_batch, values):
        if value is not None:
            chapter_values[chapter][day] = value
        elif day not in chapter_values[chapter]:
            chapter_values[chapter][day] = None


def stats_table_from_maps(
    date_order: list[str],
    chapter_values: dict[str, dict[str, int | None]],
) -> StatsTable:
    result = StatsTable(dates=list(date_order), rows=[])
    for chapter, by_date in chapter_values.items():
        row_data: dict[str, str | int | None] = {"chapter": chapter}
        for day in date_order:
            row_data[day] = by_date.get(day)
        result.rows.append(row_data)
    return result


def _sync_header_scroll(header, body_scroll, driver: WebDriver) -> None:
    if header is None:
        return
    left = driver.execute_script("return arguments[0].scrollLeft", body_scroll)
    driver.execute_script("arguments[0].scrollLeft = arguments[1]", header, left)


def _locked_body_rows(locked) -> list:
    return locked.find_elements(By.CSS_SELECTOR, "tbody tr") or locked.find_elements(By.CSS_SELECTOR, "tr")


def _scroll_body_rows(scroll) -> list:
    return scroll.find_elements(By.CSS_SELECTOR, "tbody tr") or scroll.find_elements(By.CSS_SELECTOR, "tr")


def _locked_scroll_pairs(locked, scroll) -> list[tuple[str, object]]:
    locked_rows = _locked_body_rows(locked)
    scroll_rows = _scroll_body_rows(scroll)
    locked_labels: list[str] = []
    for l_row in locked_rows:
        l_cells = _cell_texts(l_row)
        locked_labels.append(l_cells[0] if l_cells else "")
    pairs: list[tuple[str, object]] = []
    for label, scroll_idx in iter_scroll_row_indices(locked_labels):
        if scroll_idx < len(scroll_rows):
            pairs.append((label, scroll_rows[scroll_idx]))
    return pairs


def _extract_kendo_split(grid, driver: WebDriver) -> StatsTable:
    locked_els = grid.find_elements(By.CSS_SELECTOR, ".k-grid-content-locked")
    scroll_els = grid.find_elements(By.CSS_SELECTOR, ".k-grid-content.k-auto-scrollable")
    if not scroll_els:
        for el in grid.find_elements(By.CSS_SELECTOR, ".k-grid-content"):
            if "locked" not in (el.get_attribute("class") or ""):
                scroll_els.append(el)

    locked = locked_els[0] if locked_els else None
    scroll = scroll_els[0] if scroll_els else None
    header = _header_scroll_el(grid)

    if locked and scroll:
        date_order: list[str] = []
        chapter_values: dict[str, dict[str, int | None]] = {}

        driver.execute_script("arguments[0].scrollLeft = 0", scroll)
        if header is not None:
            driver.execute_script("arguments[0].scrollLeft = 0", header)
        time.sleep(SCROLL_SETTLE_S)

        last_signature = ""
        for _ in range(MAX_SCROLL_PASSES):
            dates_batch, date_indices = _visible_viewport_date_slice(driver, header, scroll)
            if not dates_batch:
                dates_batch = _visible_header_dates(grid)
                date_indices = list(range(len(dates_batch)))

            for label, s_row in _locked_scroll_pairs(locked, scroll):
                s_cells = _cell_texts(s_row)
                values = _values_for_date_indices(s_cells, date_indices)
                merge_scroll_slice(
                    date_order,
                    chapter_values,
                    chapter=label,
                    dates_batch=dates_batch,
                    values=values,
                )

            signature = ",".join(date_order)
            scroll_left = driver.execute_script("return arguments[0].scrollLeft", scroll)
            max_left = driver.execute_script(
                "return Math.max(0, arguments[0].scrollWidth - arguments[0].clientWidth)",
                scroll,
            )
            if scroll_left >= max_left and signature == last_signature:
                break
            last_signature = signature

            driver.execute_script(
                "arguments[0].scrollLeft = Math.min(arguments[0].scrollLeft + arguments[0].clientWidth, arguments[1])",
                scroll,
                max_left,
            )
            _sync_header_scroll(header, scroll, driver)
            time.sleep(SCROLL_SETTLE_S)

        if chapter_values:
            return stats_table_from_maps(date_order, chapter_values)

    result = StatsTable()
    for cell in grid.find_elements(By.CSS_SELECTOR, "th, td"):
        t = cell.text.strip()
        if _is_date_header(t) and t not in result.dates:
            result.dates.append(t)

    if locked and scroll:
        for label, s_row in _locked_scroll_pairs(locked, scroll):
            s_cells = _cell_texts(s_row)
            values = [_parse_int(v) for v in s_cells]
            row_data: dict[str, str | int | None] = {"chapter": label}
            for i, d in enumerate(result.dates):
                row_data[d] = values[i] if i < len(values) else None
            result.rows.append(row_data)

        if result.rows:
            return result

    return _extract_plain_table(grid, result)


def _extract_plain_table(table_el, result: StatsTable) -> StatsTable:
    rows = table_el.find_elements(By.CSS_SELECTOR, "tr")
    if not rows:
        return result

    header_cells = _cell_texts(rows[0])
    if not result.dates:
        for cell in header_cells[1:]:
            if _is_date_header(cell):
                result.dates.append(cell)

    for row in rows[1:]:
        cells = _cell_texts(row)
        if len(cells) < 2:
            continue
        label = cells[0]
        if not label or label == "Часть":
            continue
        if not (_is_chapter_label(label) or label == "Страница книги"):
            continue

        values = [_parse_int(v) for v in cells[1:]]
        row_data: dict[str, str | int | None] = {"chapter": label}
        for i, d in enumerate(result.dates):
            row_data[d] = values[i] if i < len(values) else None
        result.rows.append(row_data)

    return result


def parse_stats_page(driver: WebDriver, timeout: int = 30) -> StatsTable:
    """Извлечь таблицу прочтений с уже открытой страницы."""
    grid = find_best_grid(driver, timeout)
    table = _extract_kendo_split(grid, driver)
    if not table.rows:
        table = _extract_plain_table(grid, table)
    if not table.rows:
        raise RuntimeError(
            "Таблица найдена, но строки с главами не извлечены. "
            "Проверьте авторизацию и загрузку страницы."
        )
    return table
