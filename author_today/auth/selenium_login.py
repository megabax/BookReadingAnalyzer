from __future__ import annotations

from typing import Callable

from selenium.webdriver.remote.webdriver import WebDriver

from author_today.auth.login_flow import perform_login


class SeleniumLoginProvider:
    """Автоматический вход через форму author.today (+ подтверждение устройства)."""

    def __init__(
        self,
        email: str,
        password: str,
        *,
        auth_timeout: int = 120,
        code_provider: Callable[[str], str] | None = None,
    ) -> None:
        self.email = email
        self.password = password
        self.auth_timeout = auth_timeout
        self.code_provider = code_provider

    def ensure_logged_in(self, driver: WebDriver) -> None:
        perform_login(
            driver,
            self.email,
            self.password,
            auth_timeout=self.auth_timeout,
            code_provider=self.code_provider,
        )
