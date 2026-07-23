"""Вкладка «Загрузка» с author.today."""

from __future__ import annotations

import streamlit as st

from author_today.errors import DeviceCodeRequired
from author_today.services.books import load_book_catalog
from author_today.services.fetch import (
    FetchResult,
    FetchSession,
    get_session,
    register_session,
)
from author_today.ui.base import Page
from author_today.ui.components.book_load_info import BookLoadInfoPanel
from author_today.ui.components.book_picker import BookPicker
from config.settings import Settings

_SESSION_KEY = "fetch_session_id"
_HINT_KEY = "fetch_code_hint"
_RESULT_KEY = "fetch_last_result"


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
        if self._settings.headless:
            st.markdown(
                "Скачивание таблицы прочтений за период и сохранение в MS SQL. "
                "Chrome в headless (`AT_HEADLESS=1`). Для окна браузера задайте "
                "`AT_HEADLESS=0` в `.env`."
            )
        else:
            st.markdown(
                "Скачивание таблицы прочтений за период и сохранение в MS SQL. "
                "Откроется окно Chrome — при ручном входе используйте паузу ниже."
            )

        awaiting = self._active_session()
        if awaiting is not None:
            self._render_code_continue(awaiting)
            return

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
            st.caption(
                f"Браузер: **{'headless' if self._settings.headless else 'с окном'}** "
                f"(AT_HEADLESS в `.env`)."
            )
            if self._settings.has_auto_login():
                st.caption(
                    "Вход: автоматически (AT_EMAIL / AT_PASSWORD из .env). "
                    "Если сайт запросит код — появится поле ввода."
                )
            else:
                wait_login = st.number_input(
                    "Пауза для ручного входа (сек)",
                    min_value=0,
                    max_value=600,
                    value=max(self._settings.wait_login_seconds, 60),
                    help="Время на вход в author.today в открывшемся браузере.",
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
            self._start_fetch(
                book_id=book_id,
                period_start=period_start,
                period_end=period_end,
                save_mssql=save_mssql,
                save_raw=save_raw,
                wait_login_seconds=wait_login_seconds,
            )

        last_result = st.session_state.get(_RESULT_KEY)
        if isinstance(last_result, FetchResult):
            self._render_success(last_result)
            if st.button("Скрыть результат", key="fetch_clear_result"):
                st.session_state.pop(_RESULT_KEY, None)
                st.rerun()

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

    def _active_session(self) -> FetchSession | None:
        session_id = st.session_state.get(_SESSION_KEY)
        if not session_id:
            return None
        session = get_session(session_id)
        if session is None or not session.awaiting_code:
            st.session_state.pop(_SESSION_KEY, None)
            st.session_state.pop(_HINT_KEY, None)
            return None
        return session

    def _render_code_continue(self, session: FetchSession) -> None:
        hint = session.hint or st.session_state.get(_HINT_KEY) or "код подтверждения"
        st.warning(
            f"Сайт запросил **{hint}**. Браузер оставлен открытым — "
            "введите код из письма и нажмите «Продолжить»."
        )
        st.caption(
            f"book_id={session.book_id}, "
            f"{session.period_start} — {session.period_end}"
        )
        code = st.text_input(
            "Код подтверждения устройства / 2FA",
            value="",
            key="fetch_device_code_input",
            help="Код будет введён в открытое окно Chrome программно.",
        )
        col_ok, col_cancel = st.columns(2)
        with col_ok:
            continue_clicked = st.button("Продолжить", type="primary", key="fetch_continue")
        with col_cancel:
            cancel_clicked = st.button("Отменить загрузку", key="fetch_cancel")

        if cancel_clicked:
            session.close()
            st.session_state.pop(_SESSION_KEY, None)
            st.session_state.pop(_HINT_KEY, None)
            st.info("Загрузка отменена, браузер закрыт.")
            st.rerun()

        if continue_clicked:
            with st.spinner("Отправка кода и продолжение загрузки… Не закрывайте браузер."):
                try:
                    result = session.continue_with_code(code)
                except DeviceCodeRequired as exc:
                    st.session_state[_HINT_KEY] = exc.hint
                    st.error(
                        f"Снова нужен код: {exc.hint}. Проверьте код и нажмите «Продолжить»."
                    )
                    return
                except Exception as exc:
                    st.session_state.pop(_SESSION_KEY, None)
                    st.session_state.pop(_HINT_KEY, None)
                    st.error(f"Ошибка загрузки: {exc}")
                    return

            st.session_state.pop(_SESSION_KEY, None)
            st.session_state.pop(_HINT_KEY, None)
            st.session_state[_RESULT_KEY] = result
            st.rerun()

    def _start_fetch(
        self,
        *,
        book_id: int,
        period_start,
        period_end,
        save_mssql: bool,
        save_raw: bool,
        wait_login_seconds: int,
    ) -> None:
        if period_start > period_end:
            st.error("Начало периода не может быть позже конца.")
            return
        if not save_mssql and not save_raw:
            st.error("Включите сохранение в MS SQL или JSON.")
            return

        session = register_session(
            FetchSession(
                self._settings,
                book_id,
                period_start,
                period_end,
                save_mssql=save_mssql,
                save_raw=save_raw,
                wait_login_seconds=wait_login_seconds,
            )
        )

        with st.spinner(
            f"Загрузка book_id={book_id}, {period_start} — {period_end}. "
            "Не закрывайте браузер до завершения."
        ):
            try:
                result = session.start()
            except DeviceCodeRequired as exc:
                st.session_state[_SESSION_KEY] = session.session_id
                st.session_state[_HINT_KEY] = exc.hint
                st.rerun()
                return
            except Exception as exc:
                session.close()
                st.error(f"Ошибка загрузки: {exc}")
                return

        st.session_state[_RESULT_KEY] = result
        st.rerun()

    def _render_success(self, result: FetchResult) -> None:
        st.success("Загрузка завершена.")
        st.metric("Глав в таблице", result.chapter_count)
        st.metric("Дней в таблице", result.day_count)
        if result.table_date_min and result.table_date_max:
            st.caption(
                f"Даты в таблице с сайта: **{result.table_date_min}** — "
                f"**{result.table_date_max}**"
            )
            if (
                result.table_date_min > result.period_start
                or result.table_date_max < result.period_end
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
