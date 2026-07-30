"""Композиция Streamlit-приложения (DIP: страницы внедряются снаружи)."""

from __future__ import annotations

import streamlit as st

from author_today.ui.base import Page
from author_today.ui.cache import ReportCache
from author_today.ui.components.book_load_info import BookLoadInfoPanel
from author_today.ui.components.book_picker import BookPicker
from author_today.ui.components.fetch_status import render_fetch_status_banner
from author_today.ui.components.sidebar import DataSourceSidebar
from author_today.ui.pages.compare import ComparePage
from author_today.ui.pages.fetch import FetchPage
from author_today.ui.pages.funnel import FunnelPage
from author_today.ui.pages.trend import TrendPage
from config.settings import Settings


class StreamlitApp:
    """Оркестратор UI: конфиг страницы, sidebar, вкладки. Без бизнес-логики (SRP)."""

    def __init__(
        self,
        settings: Settings,
        pages: list[Page] | None = None,
        sidebar: DataSourceSidebar | None = None,
        report_cache: ReportCache | None = None,
    ) -> None:
        self._settings = settings
        self._sidebar = sidebar or DataSourceSidebar(settings)
        if pages is None:
            self._report_cache = report_cache or ReportCache(settings)
            self._pages = self._build_default_pages(settings, self._report_cache)
        else:
            self._report_cache = report_cache
            self._pages = pages

    @staticmethod
    def _build_default_pages(settings: Settings, cache: ReportCache) -> list[Page]:
        book_picker = BookPicker(settings)
        load_info = BookLoadInfoPanel(settings)
        return [
            FunnelPage(settings, book_picker, cache),
            ComparePage(settings, book_picker, cache),
            TrendPage(settings, book_picker, cache),
            FetchPage(settings, book_picker, load_info),
        ]

    def run(self) -> None:
        """Отрисовать UI. `st.set_page_config` вызывается в streamlit_app.py до импортов."""
        st.title("AuthorToday")
        st.caption("Статистика прочтений author.today")

        self._sidebar.render()
        render_fetch_status_banner(report_cache=self._report_cache)

        tabs = st.tabs([page.title for page in self._pages])
        for tab, page in zip(tabs, self._pages):
            with tab:
                page.render()


def create_app(settings: Settings | None = None) -> StreamlitApp:
    """Фабрика приложения (удобная точка для тестов и entry point)."""
    settings = settings or Settings.from_env()
    cache = ReportCache(settings)
    pages = StreamlitApp._build_default_pages(settings, cache)
    return StreamlitApp(settings, pages=pages, report_cache=cache)
