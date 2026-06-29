#!/usr/bin/env python
"""
Точка входа веб-интерфейса AutorToday.

Запуск из корня проекта:
    pip install -r requirements.txt -r requirements-ui.txt
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import streamlit as st

from author_today.services.reports import list_raw_snapshots
from config.settings import Settings

st.set_page_config(
    page_title="AutorToday",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

settings = Settings.from_env()

st.title("AutorToday")
st.caption("Статистика прочтений author.today")

st.info(
    "Интерфейс в разработке. Сейчас доступны CLI и скрипты в `scripts/`. "
    "План экранов и архитектура — в [docs/ui_streamlit.md](docs/ui_streamlit.md)."
)

with st.sidebar:
    st.header("Параметры")
    book_id = st.number_input(
        "book_id",
        min_value=1,
        value=settings.book_id,
        help="ID книги на author.today (в URL — workId)",
    )
    st.divider()
    st.subheader("Источник данных")
    if settings.has_mssql():
        st.success("MS SQL: подключение настроено")
    else:
        st.warning("MS SQL не настроен — отчёты из JSON в data/raw")
    snapshots = list_raw_snapshots(book_id=int(book_id))
    st.caption(f"JSON-снимков в data/raw: {len(snapshots)}")

tab_funnel, tab_compare, tab_fetch = st.tabs(["Воронка", "Сравнение периодов", "Загрузка"])

with tab_funnel:
    st.subheader("Воронка дочитываний")
    st.markdown(
        "Экран подключит `author_today.services.reports.load_funnel_steps` "
        "после завершения рефакторинга §2–§3 (SQL в repo, ReadSnapshot)."
    )

with tab_compare:
    st.subheader("Сравнение двух периодов")
    st.markdown(
        "Экран подключит `load_funnel_compare` (μ, σ, p-value по главам)."
    )

with tab_fetch:
    st.subheader("Загрузка с author.today")
    st.markdown(
        "Selenium-загрузка останется в CLI на первом этапе "
        "(`python selenium_stats.py`). В UI — позже, с фоновой задачей и статусом."
    )
