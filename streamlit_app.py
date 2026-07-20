#!/usr/bin/env python
"""
Точка входа веб-интерфейса AuthorToday.

Запуск из корня проекта (после `pip install -e ".[ui]"`):
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import streamlit as st

# Обязательно до импорта ui.* (там @st.cache_data) и прочих st.* вызовов.
st.set_page_config(
    page_title="AuthorToday",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

from author_today.ui.app import create_app  # noqa: E402

create_app().run()
