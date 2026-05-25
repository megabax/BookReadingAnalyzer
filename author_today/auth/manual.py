from __future__ import annotations

import time

from selenium.webdriver.remote.webdriver import WebDriver

from author_today.auth.base import AuthProvider


class ManualAuthProvider:
    """Пауза для ручного входа в браузере."""

    def __init__(self, wait_seconds: int = 0) -> None:
        self.wait_seconds = wait_seconds

    def ensure_logged_in(self, driver: WebDriver) -> None:
        if self.wait_seconds <= 0:
            return
        print(f"Войдите на author.today в браузере. Ожидание {self.wait_seconds} с...")
        time.sleep(self.wait_seconds)
