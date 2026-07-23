"""Тесты паузы загрузки на код устройства (без Selenium)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from author_today.errors import DeviceCodeRequired
from author_today.services.fetch import FetchSession, _raise_device_code_required, register_session


def test_raise_device_code_required():
    with pytest.raises(DeviceCodeRequired) as exc:
        _raise_device_code_required("код из письма")
    assert exc.value.hint == "код из письма"


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
    from config.settings import Settings

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
