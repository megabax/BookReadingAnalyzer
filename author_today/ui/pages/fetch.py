"""Вкладка «Загрузка» с author.today (фоновый FetchJob)."""

from __future__ import annotations

import streamlit as st

from author_today.services.books import load_book_catalog
from author_today.services.fetch import FetchJob, FetchResult, register_job
from author_today.ui.base import Page
from author_today.ui.components.book_load_info import BookLoadInfoPanel
from author_today.ui.components.book_picker import BookPicker
from author_today.ui.components.fetch_status import (
    RESULT_STATE_KEY,
    bind_job,
    clear_job_binding,
    resolve_job,
)
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
        if self._settings.headless:
            st.markdown(
                "Скачивание таблицы прочтений за период и сохранение в MS SQL. "
                "Загрузка идёт в фоне (`AT_HEADLESS=1`). Для окна браузера задайте "
                "`AT_HEADLESS=0` в `.env`."
            )
        else:
            st.markdown(
                "Скачивание таблицы прочтений за период и сохранение в MS SQL. "
                "Загрузка идёт в фоне; при необходимости откроется окно Chrome."
            )

        job = resolve_job()
        if job is not None:
            progress = job.snapshot()
            if progress.is_active or progress.status in ("done", "error", "cancelled"):
                self._render_job_panel(job)
                if progress.is_active or progress.status in ("error", "cancelled"):
                    return
                # done — ниже можно показать детали результата и форму новой загрузки

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
                f"(AT_HEADLESS в `.env`). Загрузка — фоновая задача."
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

        start_disabled = bool(job and job.snapshot().is_active)
        if st.button(
            "Загрузить период",
            type="primary",
            icon="⬇️",
            disabled=start_disabled,
        ):
            self._start_fetch(
                book_id=book_id,
                period_start=period_start,
                period_end=period_end,
                save_mssql=save_mssql,
                save_raw=save_raw,
                wait_login_seconds=wait_login_seconds,
            )

        last_result = st.session_state.get(RESULT_STATE_KEY)
        if isinstance(last_result, FetchResult):
            self._render_success(last_result)
            if st.button("Скрыть результат", key="fetch_clear_result"):
                st.session_state.pop(RESULT_STATE_KEY, None)
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

    def _render_job_panel(self, job: FetchJob) -> None:
        progress = job.snapshot()
        st.markdown("### Статус загрузки")
        st.caption(
            f"book_id={progress.book_id} · "
            f"{progress.period_start} — {progress.period_end} · "
            f"порции {progress.chunk_label}"
        )
        st.progress(progress.fraction)
        st.write(progress.stage)

        if progress.status == "running":
            st.info("Загрузка выполняется в фоне — можно открыть «Воронку» или «Сравнение».")
            if st.button("Отменить", key="fetch_page_cancel_running"):
                job.cancel()
                st.rerun()
            return

        if progress.status == "awaiting_code":
            hint = progress.hint or "код подтверждения"
            st.warning(
                f"Сайт запросил **{hint}**. Браузер (или headless-сессия) ждёт код — "
                "введите его и нажмите «Продолжить»."
            )
            code = st.text_input(
                "Код подтверждения устройства / 2FA",
                value="",
                key="fetch_device_code_input",
            )
            col_ok, col_cancel = st.columns(2)
            with col_ok:
                continue_clicked = st.button(
                    "Продолжить",
                    type="primary",
                    key="fetch_continue",
                )
            with col_cancel:
                cancel_clicked = st.button("Отменить загрузку", key="fetch_cancel")

            if cancel_clicked:
                job.cancel()
                st.rerun()
            if continue_clicked:
                try:
                    job.submit_code(code)
                except ValueError as exc:
                    st.error(str(exc))
                    return
                st.toast("Код отправлен, загрузка продолжается…")
                st.rerun()
            return

        if progress.status == "done" and progress.result is not None:
            st.session_state[RESULT_STATE_KEY] = progress.result
            st.success("Фоновая загрузка завершена.")
            if st.button("Закрыть статус задачи", key="fetch_page_dismiss_done"):
                job.dismiss()
                clear_job_binding()
                st.rerun()
            return

        if progress.status == "error":
            st.error(progress.error or "Ошибка загрузки")
            if st.button("Закрыть", key="fetch_page_dismiss_error"):
                job.dismiss()
                clear_job_binding()
                st.rerun()
            return

        if progress.status == "cancelled":
            st.warning("Загрузка отменена.")
            if st.button("Закрыть", key="fetch_page_dismiss_cancelled"):
                job.dismiss()
                clear_job_binding()
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

        existing = resolve_job()
        if existing is not None and existing.snapshot().is_active:
            st.warning("Уже есть активная загрузка. Дождитесь завершения или отмените её.")
            return

        job = register_job(
            FetchJob(
                self._settings,
                book_id,
                period_start,
                period_end,
                save_mssql=save_mssql,
                save_raw=save_raw,
                wait_login_seconds=wait_login_seconds,
            )
        )
        bind_job(job)
        job.start()
        st.toast("Загрузка запущена в фоне")
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
