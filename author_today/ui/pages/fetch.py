"""Вкладка «Загрузка» с author.today."""

from __future__ import annotations

import streamlit as st

from author_today.services.books import load_book_catalog
from author_today.services.fetch import fetch_reads_for_period
from author_today.ui.base import Page
from author_today.ui.components.book_load_info import BookLoadInfoPanel
from author_today.ui.components.book_picker import BookPicker
from config.settings import Settings


class FetchPage(Page):
    """Экран загрузки статистики через Selenium."""

    def __init__(
        self,
        settings: Settings,
        book_picker: BookPicker,
        load_info: BookLoadInfoPanel | None = None,
    ) -> None:
        self._settings = settings
        self._book_picker = book_picker
        self._load_info = load_info or BookLoadInfoPanel(settings)

    @property
    def title(self) -> str:
        return "Загрузка"

    def render(self) -> None:
        st.subheader("Загрузка с author.today")
        st.markdown(
            "Скачивание таблицы прочтений за период и сохранение в MS SQL. "
            "Откроется окно Chrome — при ручном входе используйте паузу ниже."
        )

        catalog = load_book_catalog(self._settings)
        book_id = self._book_picker.pick(catalog, key_prefix="fetch")
        self._load_info.render(book_id)

        col_start, col_end = st.columns(2)
        with col_start:
            period_start = st.date_input(
                "Начало периода",
                value=self._settings.default_period_start,
            )
        with col_end:
            period_end = st.date_input(
                "Конец периода",
                value=self._settings.default_period_end,
            )

        wait_login = 0
        with st.expander("Авторизация и опции", expanded=not self._settings.has_auto_login()):
            if self._settings.has_auto_login():
                st.caption("Вход: автоматически (AT_EMAIL / AT_PASSWORD из .env).")
            else:
                wait_login = st.number_input(
                    "Пауза для ручного входа (сек)",
                    min_value=0,
                    max_value=600,
                    value=max(self._settings.wait_login_seconds, 60),
                    help="Время на вход в author.today в открывшемся браузере.",
                )
            device_code = st.text_input(
                "Код подтверждения устройства / 2FA",
                value="",
                help="Если author.today запросит код с почты — введите заранее или повторите загрузку.",
            )
            save_mssql = st.checkbox(
                "Сохранить в MS SQL",
                value=self._settings.has_mssql(),
                disabled=not self._settings.has_mssql(),
            )
            save_raw = st.checkbox(
                "Сохранить JSON в data/raw (legacy)",
                value=False,
            )

        wait_login_seconds = (
            int(wait_login)
            if not self._settings.has_auto_login()
            else self._settings.wait_login_seconds
        )

        if st.button("Загрузить период", type="primary", icon="⬇️"):
            self._run_fetch(
                book_id=book_id,
                period_start=period_start,
                period_end=period_end,
                save_mssql=save_mssql,
                save_raw=save_raw,
                wait_login_seconds=wait_login_seconds,
                device_code=device_code or None,
            )

        if catalog:
            with st.expander("Книги в каталоге"):
                st.dataframe(
                    [
                        {
                            "book_id": book.book_id,
                            "title": book.title or "",
                            "в БД": "да" if book.in_database else "",
                            "в books.yaml": "да" if book.in_yaml else "",
                        }
                        for book in catalog
                    ],
                    hide_index=True,
                    width="stretch",
                )

    def _run_fetch(
        self,
        *,
        book_id: int,
        period_start,
        period_end,
        save_mssql: bool,
        save_raw: bool,
        wait_login_seconds: int,
        device_code: str | None,
    ) -> None:
        if period_start > period_end:
            st.error("Начало периода не может быть позже конца.")
            return
        if not save_mssql and not save_raw:
            st.error("Включите сохранение в MS SQL или JSON.")
            return

        with st.spinner(
            f"Загрузка book_id={book_id}, {period_start} — {period_end}. "
            "Не закрывайте браузер до завершения."
        ):
            try:
                result = fetch_reads_for_period(
                    self._settings,
                    book_id,
                    period_start,
                    period_end,
                    save_mssql=save_mssql,
                    save_raw=save_raw,
                    wait_login_seconds=wait_login_seconds,
                    device_code=device_code,
                )
            except Exception as exc:
                st.error(f"Ошибка загрузки: {exc}")
                return

        st.success("Загрузка завершена.")
        st.metric("Глав в таблице", result.chapter_count)
        st.metric("Дней в таблице", result.day_count)
        if result.table_date_min and result.table_date_max:
            st.caption(
                f"Даты в таблице с сайта: **{result.table_date_min}** — "
                f"**{result.table_date_max}**"
            )
            if (
                result.table_date_min > period_start
                or result.table_date_max < period_end
            ):
                st.warning(
                    "С сайта пришли не все дни запрошенного периода. "
                    "Возможные причины: нет статистики в начале периода "
                    "или таблица на сайте обрезана. Повторите загрузку; "
                    "при необходимости удалите неполный run через "
                    "`scripts/delete_runs.py`."
                )
        if result.monthly_chunks > 1:
            st.info(
                f"Период разбит на {result.monthly_chunks} месяц(ев); "
                "в БД сохранены все порции."
            )
        if result.saved_mssql:
            st.caption("Данные записаны в MS SQL (fetch_runs + chapter_reads).")
        if result.saved_raw:
            st.caption("Копия снимка сохранена в data/raw.")
        st.caption(
            "Сообщение `ConnectionResetError` в консоли после загрузки на Windows "
            "обычно безвредно — это закрытие канала Chrome/Selenium."
        )
        st.rerun()
