"""Шаги авторизации author.today (форма входа, 2FA, новое устройство)."""

from __future__ import annotations

import time
from typing import Callable

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

DEVICE_CONFIRM_MARKER = "Подтверждение входа с нового устройства"
TWO_FACTOR_MARKER = "Двухфакторная аутентификация"


def _visible_elements(driver: WebDriver, by: By, value: str):
    return [el for el in driver.find_elements(by, value) if el.is_displayed()]


def login_form_visible(driver: WebDriver) -> bool:
    return bool(_visible_elements(driver, By.ID, "Login"))


def device_confirmation_visible(driver: WebDriver) -> bool:
    xpath = f"//label[contains(normalize-space(.), '{DEVICE_CONFIRM_MARKER}')]"
    return any(el.is_displayed() for el in driver.find_elements(By.XPATH, xpath))


def two_factor_visible(driver: WebDriver) -> bool:
    xpath = f"//label[contains(normalize-space(.), '{TWO_FACTOR_MARKER}')]"
    return any(el.is_displayed() for el in driver.find_elements(By.XPATH, xpath))


def confirmation_code_visible(driver: WebDriver) -> bool:
    return device_confirmation_visible(driver) or two_factor_visible(driver)


def is_authenticated(driver: WebDriver) -> bool:
    url = driver.current_url.lower()
    if "/account/login" in url:
        return False
    if login_form_visible(driver):
        return False
    if confirmation_code_visible(driver):
        return False
    return True


def _visible_login_input(driver: WebDriver):
    for el in driver.find_elements(By.ID, "Login"):
        if el.is_displayed():
            return el
    return None


def _visible_password_input(driver: WebDriver):
    for el in driver.find_elements(By.CSS_SELECTOR, "input[type='password']"):
        if el.is_displayed():
            return el
    return None


def _visible_code_input(driver: WebDriver):
    for el in driver.find_elements(By.NAME, "Code"):
        if el.is_displayed():
            return el
    return None


def _visible_submit_button(driver: WebDriver):
    for btn in driver.find_elements(By.CSS_SELECTOR, "#loginForm button[type='submit']"):
        if btn.is_displayed() and "Войти" in (btn.text or ""):
            return btn
    for btn in driver.find_elements(By.CSS_SELECTOR, "button[type='submit'].btn-primary"):
        if btn.is_displayed():
            return btn
    return None


def _type_input(element, text: str) -> None:
    element.clear()
    element.click()
    element.send_keys(text)


def submit_login_form(driver: WebDriver, login: str, password: str) -> None:
    login_input = _visible_login_input(driver)
    password_input = _visible_password_input(driver)
    if not login_input or not password_input:
        raise RuntimeError("Форма входа не найдена на странице.")

    _type_input(login_input, login)
    _type_input(password_input, password)

    submit = _visible_submit_button(driver)
    if not submit:
        raise RuntimeError("Кнопка «Войти» не найдена.")
    submit.click()


def submit_confirmation_code(driver: WebDriver, code: str) -> None:
    code_input = _visible_code_input(driver)
    if not code_input:
        raise RuntimeError("Поле кода подтверждения не найдено.")

    _type_input(code_input, code)

    submit = _visible_submit_button(driver)
    if not submit:
        raise RuntimeError("Кнопка подтверждения не найдена.")
    submit.click()


def prompt_confirmation_code(driver: WebDriver, code_provider: Callable[[str], str] | None = None) -> str:
    if device_confirmation_visible(driver):
        hint = "код подтверждения нового устройства (из письма)"
    elif two_factor_visible(driver):
        hint = "код двухфакторной аутентификации"
    else:
        hint = "код подтверждения"

    if code_provider:
        return code_provider(hint).strip()

    return input(f"Введите {hint}: ").strip()


def wait_until_authenticated(driver: WebDriver, timeout: int) -> None:
    WebDriverWait(driver, timeout).until(lambda d: is_authenticated(d))


def wait_for_login_or_confirmation(driver: WebDriver, timeout: int) -> None:
    def login_or_confirm(drv: WebDriver) -> bool:
        return (
            login_form_visible(drv)
            or confirmation_code_visible(drv)
            or is_authenticated(drv)
        )

    WebDriverWait(driver, timeout).until(login_or_confirm)


def perform_login(
    driver: WebDriver,
    login: str,
    password: str,
    *,
    auth_timeout: int = 120,
    code_provider: Callable[[str], str] | None = None,
) -> None:
    """
    Полный цикл: логин/пароль → код нового устройства или 2FA → ожидание входа.
    """
    if is_authenticated(driver):
        return

    wait_for_login_or_confirmation(driver, auth_timeout)

    if login_form_visible(driver):
        submit_login_form(driver, login, password)
        try:
            WebDriverWait(driver, 20).until(
                lambda d: confirmation_code_visible(d)
                or is_authenticated(d)
                or not login_form_visible(d)
            )
        except TimeoutException:
            pass

    deadline = time.time() + auth_timeout
    while time.time() < deadline:
        if is_authenticated(driver):
            return

        if confirmation_code_visible(driver):
            code = prompt_confirmation_code(driver, code_provider)
            if not code:
                raise RuntimeError("Код подтверждения не введён.")
            submit_confirmation_code(driver, code)
            time.sleep(1)
            continue

        if login_form_visible(driver):
            raise RuntimeError(
                "Авторизация не удалась. Проверьте AT_EMAIL и AT_PASSWORD в .env"
            )

        time.sleep(0.5)

    try:
        wait_until_authenticated(driver, 5)
    except TimeoutException as exc:
        raise TimeoutException(
            f"Не удалось завершить вход за {auth_timeout} с. "
            "Возможно, требуется код подтверждения или капча."
        ) from exc
