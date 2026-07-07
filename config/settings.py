from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def load_dotenv() -> None:
    """Загрузить .env из корня проекта (если есть)."""
    env_path = ROOT_DIR / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


DEFAULT_STATS_URL = (
    "https://author.today/report/work/stats?"
    "startDate=2025-07-01T20%3A00%3A00.000Z&endDate=2025-07-31T19%3A59%3A59.000Z"
    "&workId=323389&valueType=hit"
)
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
REPORTS_DIR = DATA_DIR / "reports"
DB_PATH = DATA_DIR / "db" / "reads.sqlite"


def previous_month_period(today: date | None = None) -> tuple[date, date]:
    """Первый и последний день прошлого месяца."""
    today = today or date.today()
    current_month_start = today.replace(day=1)
    prev_month_end = current_month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)
    return prev_month_start, prev_month_end


DEFAULT_PERIOD_START, DEFAULT_PERIOD_END = previous_month_period()


@dataclass
class Settings:
    default_stats_url: str = DEFAULT_STATS_URL
    default_period_start: date = field(default_factory=lambda: previous_month_period()[0])
    default_period_end: date = field(default_factory=lambda: previous_month_period()[1])
    book_id: int = 323389
    value_type: str = "hit"
    chrome_user_data_dir: str | None = None
    headless: bool = False
    page_timeout: int = 45
    wait_login_seconds: int = 0
    auth_timeout: int = 120
    at_email: str | None = None
    at_password: str | None = None
    mssql_connection_string: str | None = None
    mssql_server: str | None = None
    mssql_database: str | None = None
    mssql_user: str | None = None
    mssql_password: str | None = None
    mssql_driver: str = "ODBC Driver 17 for SQL Server"
    mssql_trusted_connection: bool = False
    mssql_trust_server_certificate: bool = True
    enable_legacy_json: bool = False

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv()
        book_id_raw = os.getenv("AT_BOOK_ID") or os.getenv("AT_WORK_ID") or "323389"
        return cls(
            book_id=int(book_id_raw),
            value_type=os.getenv("AT_VALUE_TYPE", "hit"),
            chrome_user_data_dir=os.getenv("CHROME_USER_DATA_DIR") or None,
            headless=os.getenv("AT_HEADLESS", "").lower() in ("1", "true", "yes"),
            page_timeout=int(os.getenv("AT_PAGE_TIMEOUT", "45")),
            wait_login_seconds=int(os.getenv("AT_WAIT_LOGIN", "0")),
            auth_timeout=int(os.getenv("AT_AUTH_TIMEOUT", "120")),
            at_email=os.getenv("AT_EMAIL") or None,
            at_password=os.getenv("AT_PASSWORD") or None,
            mssql_connection_string=os.getenv("MSSQL_CONNECTION_STRING") or None,
            mssql_server=os.getenv("MSSQL_SERVER") or None,
            mssql_database=os.getenv("MSSQL_DATABASE") or None,
            mssql_user=os.getenv("MSSQL_USER") or None,
            mssql_password=os.getenv("MSSQL_PASSWORD") or None,
            mssql_driver=os.getenv("MSSQL_DRIVER", "ODBC Driver 17 for SQL Server"),
            mssql_trusted_connection=os.getenv("MSSQL_TRUSTED_CONNECTION", "")
            .lower()
            in ("1", "true", "yes"),
            mssql_trust_server_certificate=os.getenv("MSSQL_TRUST_SERVER_CERTIFICATE", "yes")
            .lower()
            not in ("0", "false", "no"),
            enable_legacy_json=os.getenv("AT_ENABLE_LEGACY_JSON", "")
            .lower()
            in ("1", "true", "yes"),
        )

    def has_auto_login(self) -> bool:
        return bool(self.at_email and self.at_password)

    def has_mssql(self) -> bool:
        if self.mssql_connection_string:
            return True
        if not self.mssql_server or not self.mssql_database:
            return False
        if self.mssql_trusted_connection:
            return True
        return bool(self.mssql_user and self.mssql_password)


def ensure_data_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
