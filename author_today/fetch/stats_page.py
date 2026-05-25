from __future__ import annotations

from selenium.webdriver.remote.webdriver import WebDriver

from author_today.auth.base import AuthProvider
from author_today.domain.models import StatsTable
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
    auth.ensure_logged_in(driver)
    if url not in driver.current_url:
        driver.get(url)
    return parse_stats_page(driver, timeout=timeout)
