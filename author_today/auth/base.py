from __future__ import annotations

from typing import Protocol

from selenium.webdriver.remote.webdriver import WebDriver


class AuthProvider(Protocol):
    """Обеспечить авторизацию на author.today перед загрузкой статистики."""

    def ensure_logged_in(self, driver: WebDriver) -> None: ...
