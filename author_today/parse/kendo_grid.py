"""Парсинг Kendo Grid со страницы статистики author.today."""

from __future__ import annotations

import re

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait

from author_today.domain.models import StatsTable

DATE_RE = re.compile(r"^\d{2}\.\d{2}$")
CHAPTER_MARKERS = ("глава", "интерлюдия", "страница книги", "вместо эпилога", "часть")


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


def _extract_kendo_split(grid) -> StatsTable:
    result = StatsTable()

    for cell in grid.find_elements(By.CSS_SELECTOR, "th, td"):
        t = cell.text.strip()
        if _is_date_header(t) and t not in result.dates:
            result.dates.append(t)

    locked_els = grid.find_elements(By.CSS_SELECTOR, ".k-grid-content-locked")
    scroll_els = grid.find_elements(By.CSS_SELECTOR, ".k-grid-content.k-auto-scrollable")
    if not scroll_els:
        for el in grid.find_elements(By.CSS_SELECTOR, ".k-grid-content"):
            if "locked" not in (el.get_attribute("class") or ""):
                scroll_els.append(el)

    locked = locked_els[0] if locked_els else None
    scroll = scroll_els[0] if scroll_els else None

    if locked and scroll:
        locked_rows = locked.find_elements(By.CSS_SELECTOR, "tbody tr") or locked.find_elements(
            By.CSS_SELECTOR, "tr"
        )
        scroll_rows = scroll.find_elements(By.CSS_SELECTOR, "tbody tr") or scroll.find_elements(
            By.CSS_SELECTOR, "tr"
        )

        for l_row, s_row in zip(locked_rows, scroll_rows):
            l_cells = _cell_texts(l_row)
            s_cells = _cell_texts(s_row)
            if not l_cells:
                continue
            label = l_cells[0]
            if not label or label == "Часть":
                continue
            if not _is_chapter_label(label) and label != "Страница книги":
                continue

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
    table = _extract_kendo_split(grid)
    if not table.rows:
        table = _extract_plain_table(grid, table)
    if not table.rows:
        raise RuntimeError(
            "Таблица найдена, но строки с главами не извлечены. "
            "Проверьте авторизацию и загрузку страницы."
        )
    return table
