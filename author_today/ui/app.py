"""Композиция Streamlit-приложения (DIP: страницы внедряются снаружи)."""

from __future__ import annotations

import streamlit as st

from author_today.ui.base import Page
from author_today.ui.cache import ReportCache
from author_today.ui.components.book_load_info import BookLoadInfoPanel
from author_today.ui.components.book_picker import BookPicker
from author_today.ui.components.sidebar import DataSourceSidebar
from author_today.ui.pages.compare import ComparePage
from author_today.ui.pages.fetch import FetchPage
from author_today.ui.pages.funnel import FunnelPage
from config.settings import Settings


class StreamlitApp:
    """Оркестратор UI: конфиг страницы, sidebar, вкладки. Без бизнес-логики (SRP)."""

    def __init__(
        self,
        settings: Settings,
        pages: list[Page] | None = None,
        sidebar: DataSourceSidebar | None = None,
    ) -> None:
        self._settings = settings
        self._sidebar = sidebar or DataSourceSidebar(settings)
        self._pages = pages if pages is not None else self._default_pages(settings)

    @staticmethod
    def _default_pages(settings: Settings) -> list[Page]:
        cache = ReportCache(settings)
        book_picker = BookPicker(settings)
        load_info = BookLoadInfoPanel(settings)
        return [
            FunnelPage(settings, book_picker, cache),
            ComparePage(settings, book_picker, cache),
            FetchPage(settings, book_picker, load_info),
        ]

    def run(self) -> None:
        """Отрисовать UI. `st.set_page_config` вызывается в streamlit_app.py до импортов."""
        st.title("AuthorToday")
        st.caption("Статистика прочтений author.today")

        self._sidebar.render()

        tabs = st.tabs([page.title for page in self._pages])
        for tab, page in zip(tabs, self._pages):
            with tab:
                page.render()


def create_app(settings: Settings | None = None) -> StreamlitApp:
    """Фабрика приложения (удобная точка для тестов и entry point)."""
    return StreamlitApp(settings or Settings.from_env())
