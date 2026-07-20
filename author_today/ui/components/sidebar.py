"""Боковая панель: статус источника данных."""

from __future__ import annotations

import streamlit as st

from config.settings import Settings


class DataSourceSidebar:
    """Отвечает только за индикатор MS SQL в sidebar (SRP)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def render(self) -> None:
        with st.sidebar:
            st.header("Источник данных")
            if self._settings.has_mssql():
                st.success("MS SQL — актуальные данные")
            else:
                st.error("MS SQL не настроен. Задайте MSSQL_* в .env")
