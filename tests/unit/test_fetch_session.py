"""Тесты FetchSession / FetchJob (без реального Selenium)."""

from __future__ import annotations

import time
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from author_today.errors import DeviceCodeRequired
from author_today.services.fetch import (
    FetchJob,
    FetchProgress,
    FetchSession,
    _raise_device_code_required,
    register_job,
    register_session,
)
from config.settings import Settings


def test_raise_device_code_required():
    with pytest.raises(DeviceCodeRequired) as exc:
        _raise_device_code_required("код из письма")
    assert exc.value.hint == "код из письма"


def test_fetch_progress_fraction():
    p = FetchProgress(status="running", current_chunk=2, total_chunks=4)
    assert p.fraction == 0.5
    assert p.chunk_label == "2/4"
    assert FetchProgress(status="done").fraction == 1.0
    assert FetchProgress(status="awaiting_code").is_active


def test_fetch_session_rejects_inverted_period():
    settings = MagicMock()
    settings.has_mssql.return_value = True
    with pytest.raises(ValueError, match="не позже"):
        FetchSession(
            settings,
            1,
            date(2025, 2, 1),
            date(2025, 1, 1),
            save_mssql=False,
        )


def test_fetch_session_start_keeps_driver_on_device_code():
    settings = Settings(
        book_id=1,
        at_email="a@b.c",
        at_password="x",
        mssql_server=None,
        mssql_database=None,
    )
    driver = MagicMock()
    session = register_session(
        FetchSession(
            settings,
            42,
            date(2025, 1, 1),
            date(2025, 1, 31),
            save_mssql=False,
            save_raw=False,
        )
    )

    with (
        patch("author_today.services.fetch.create_driver", return_value=driver),
        patch(
            "author_today.services.fetch._load_and_persist_period",
            side_effect=DeviceCodeRequired("код подтверждения нового устройства"),
        ),
    ):
        with pytest.raises(DeviceCodeRequired):
            session.start()

    assert session.awaiting_code
    assert session._driver is driver
    assert "нового устройства" in (session.hint or "")

    session.close()
    assert session._driver is None
    driver.quit.assert_called_once()


def test_fetch_job_awaits_code_then_completes():
    settings = Settings(
        book_id=1,
        at_email="a@b.c",
        at_password="x",
        mssql_server=None,
        mssql_database=None,
    )
    driver = MagicMock()
    table = MagicMock()
    table.rows = [1, 2]
    table.dates = ["01.01", "02.01"]

    class FakeAuth:
        def __init__(self, code_provider):
            self.code_provider = code_provider
            self.asked = False

        def ensure_logged_in(self, _driver):
            if not self.asked:
                self.asked = True
                self.code_provider("код из письма")

    def fake_auth_provider(settings, *, device_code_provider=None, wait_login_seconds=None):
        return FakeAuth(device_code_provider)

    def fake_load(driver, auth, settings, period_start, period_end, **_kwargs):
        auth.ensure_logged_in(driver)
        return table

    job = register_job(
        FetchJob(
            settings,
            42,
            date(2025, 1, 1),
            date(2025, 1, 31),
            save_mssql=False,
            save_raw=False,
        )
    )

    with (
        patch("author_today.services.fetch.create_driver", return_value=driver),
        patch("author_today.services.fetch._auth_provider", side_effect=fake_auth_provider),
        patch(
            "author_today.services.fetch._load_and_persist_period",
            side_effect=fake_load,
        ),
        patch(
            "author_today.services.fetch.parse_dd_mm_columns",
            return_value=[date(2025, 1, 1), date(2025, 1, 2)],
        ),
    ):
        job.start()
        deadline = time.time() + 5
        while time.time() < deadline and job.snapshot().status != "awaiting_code":
            time.sleep(0.05)
        assert job.snapshot().status == "awaiting_code"
        assert "письма" in (job.snapshot().hint or "")

        job.submit_code("123456")
        deadline = time.time() + 5
        while time.time() < deadline and job.snapshot().status not in (
            "done",
            "error",
            "cancelled",
        ):
            time.sleep(0.05)

        snap = job.snapshot()
        assert snap.status == "done", snap.error
        assert snap.result is not None
        assert snap.result.chapter_count == 2
        assert snap.fraction == 1.0
        driver.quit.assert_called()
        job.dismiss()
