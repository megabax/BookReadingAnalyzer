from __future__ import annotations

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote.webdriver import WebDriver

from config.settings import Settings


def create_driver(settings: Settings) -> WebDriver:
    options = Options()
    if settings.headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1400,900")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    if settings.chrome_user_data_dir:
        options.add_argument(f"--user-data-dir={settings.chrome_user_data_dir}")
    return webdriver.Chrome(options=options)
