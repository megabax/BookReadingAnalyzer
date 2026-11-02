from __future__ import annotations

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.remote.webdriver import WebDriver

from author_today.auth.base import AuthProvider
from author_today.domain.models import StatsTable
from author_today.fetch.page_errors import raise_if_stats_page_error
from author_today.parse.kendo_grid import parse_stats_page


def load_stats_table(
    driver: WebDriver,
    url: str,
    auth: AuthProvider,
    *,
    timeout: int = 45,
) -> StatsTable:
    """Открыть страницу, авторизоваться и распарсить таблицу."""
    driver.get(url)
    try:
        auth.ensure_logged_in(driver)
    except TimeoutException as exc:
        detail = str(exc).strip()
        if not detail or detail in {"Message:", "Message"}:
            detail = (
                "Таймаут при входе на author.today "
                "(AT_AUTH_TIMEOUT / код устройства / headless)."
            )
        raise TimeoutException(detail) from exc
    if url not in driver.current_url:
        driver.get(url)
    # Сначала ошибка доступа/404 — не ждать Kendo ~timeout секунд
    raise_if_stats_page_error(driver.page_source or "")
    try:
        return parse_stats_page(driver, timeout=timeout)
    except TimeoutException as exc:
        # Сообщение уже могло быть задано в find_best_grid; дополняем URL.
        detail = str(exc).strip()
        if not detail or detail in {"Message:", "Message"}:
            detail = (
                f"Таблица статистики не появилась за {timeout} с "
                f"(AT_PAGE_TIMEOUT)."
            )
        raise TimeoutException(f"{detail} URL: {url}") from exc
