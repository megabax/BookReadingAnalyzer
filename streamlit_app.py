#!/usr/bin/env python
"""
Точка входа веб-интерфейса AutorToday.

Запуск из корня проекта:
    pip install -r requirements.txt -r requirements-ui.txt
    streamlit run streamlit_app.py
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from author_today.services.books import BookOption, load_book_catalog, load_book_data_info
from author_today.services.fetch import fetch_reads_for_period
from config.settings import Settings

st.set_page_config(
    page_title="AutorToday",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

settings = Settings.from_env()


def _resolve_book_id_from_catalog(catalog: list[BookOption], label: str) -> int:
    for book in catalog:
        if book.label == label:
            return book.book_id
    raise ValueError(f"Неизвестная книга в списке: {label}")


def _render_book_load_info(book_id: int) -> None:
    if not settings.has_mssql():
        return

    info = load_book_data_info(settings, book_id)
    if info is None:
        return

    st.markdown("**Уже загружено в БД**")
    if not info.runs and info.read_date_min is None:
        st.info(f"По book_id={book_id} в MS SQL пока нет снимков.")
        return

    if info.read_date_min and info.read_date_max:
        st.caption(
            f"Покрытие по дням прочтений (chapter_reads): "
            f"**{info.read_date_min}** — **{info.read_date_max}**"
        )

    if info.runs:
        st.dataframe(
            [
                {
                    "run_id": run.run_id,
                    "период с": run.period_start,
                    "период по": run.period_end,
                    "загружено": run.fetched_at.strftime("%Y-%m-%d %H:%M"),
                }
                for run in info.runs
            ],
            hide_index=True,
            width="stretch",
        )
        st.caption(
            "В отчётах за произвольный период суммируются все run'ы, "
            "попадающие в выбранные даты read_date."
        )
    elif info.read_date_min:
        st.caption("Записи fetch_runs не найдены, но строки chapter_reads есть.")


st.title("AutorToday")
st.caption("Статистика прочтений author.today")

with st.sidebar:
    st.header("Источник данных")
    if settings.has_mssql():
        st.success("MS SQL — актуальные данные")
    else:
        st.error("MS SQL не настроен. Задайте MSSQL_* в .env")

tab_funnel, tab_compare, tab_fetch = st.tabs(["Воронка", "Сравнение периодов", "Загрузка"])

with tab_funnel:
    st.subheader("Воронка дочитываний")
    st.markdown(
        "Экран подключит `author_today.services.reports.load_funnel_steps` "
        "(repo → ReadSnapshot → analyze)."
    )

with tab_compare:
    st.subheader("Сравнение двух периодов")
    st.markdown(
        "Экран подключит `load_funnel_compare` (μ, σ, p-value по главам)."
    )

with tab_fetch:
    st.subheader("Загрузка с author.today")
    st.markdown(
        "Скачивание таблицы прочтений за период и сохранение в MS SQL. "
        "Откроется окно Chrome — при ручном входе используйте паузу ниже."
    )

    catalog = load_book_catalog(settings)

    book_mode = st.radio(
        "Книга",
        options=["Из списка", "Новый book_id"],
        horizontal=True,
        help="Список: config/books.yaml и книги из БД. Новый ID можно загрузить до появления в каталоге.",
    )

    selected_book_id: int
    if book_mode == "Из списка":
        if catalog:
            labels = [book.label for book in catalog]
            default_label = next(
                (book.label for book in catalog if book.book_id == settings.book_id),
                labels[0],
            )
            picked = st.selectbox("Выберите книгу", options=labels, index=labels.index(default_label))
            selected_book_id = _resolve_book_id_from_catalog(catalog, picked)
        else:
            st.info("Каталог пуст. Добавьте книги в `config/books.yaml` или выберите «Новый book_id».")
            selected_book_id = int(
                st.number_input(
                    "book_id",
                    min_value=1,
                    value=settings.book_id,
                    step=1,
                )
            )
    else:
        selected_book_id = int(
            st.number_input(
                "book_id (workId в URL author.today)",
                min_value=1,
                value=settings.book_id,
                step=1,
            )
        )
        known_ids = {book.book_id for book in catalog}
        if selected_book_id in known_ids:
            st.caption("Эта книга уже есть в каталоге / БД.")
        else:
            st.caption("Новая книга: запись в `dbo.books` создастся при сохранении снимка.")

    _render_book_load_info(selected_book_id)

    col_start, col_end = st.columns(2)
    with col_start:
        period_start = st.date_input(
            "Начало периода",
            value=settings.default_period_start,
        )
    with col_end:
        period_end = st.date_input(
            "Конец периода",
            value=settings.default_period_end,
        )

    with st.expander("Авторизация и опции", expanded=not settings.has_auto_login()):
        if settings.has_auto_login():
            st.caption("Вход: автоматически (AT_EMAIL / AT_PASSWORD из .env).")
        else:
            wait_login = st.number_input(
                "Пауза для ручного входа (сек)",
                min_value=0,
                max_value=600,
                value=max(settings.wait_login_seconds, 60),
                help="Время на вход в author.today в открывшемся браузере.",
            )
        device_code = st.text_input(
            "Код подтверждения устройства / 2FA",
            value="",
            help="Если author.today запросит код с почты — введите заранее или повторите загрузку.",
        )
        save_mssql = st.checkbox(
            "Сохранить в MS SQL",
            value=settings.has_mssql(),
            disabled=not settings.has_mssql(),
        )
        save_raw = st.checkbox(
            "Сохранить JSON в data/raw (legacy)",
            value=False,
        )

    if not settings.has_auto_login():
        wait_login_seconds = int(wait_login)
    else:
        wait_login_seconds = settings.wait_login_seconds

    if st.button("Загрузить период", type="primary", icon="⬇️"):
        if period_start > period_end:
            st.error("Начало периода не может быть позже конца.")
        elif not save_mssql and not save_raw:
            st.error("Включите сохранение в MS SQL или JSON.")
        else:
            with st.spinner(
                f"Загрузка book_id={selected_book_id}, {period_start} — {period_end}. "
                "Не закрывайте браузер до завершения."
            ):
                try:
                    result = fetch_reads_for_period(
                        settings,
                        selected_book_id,
                        period_start,
                        period_end,
                        save_mssql=save_mssql,
                        save_raw=save_raw,
                        wait_login_seconds=wait_login_seconds,
                        device_code=device_code or None,
                    )
                except Exception as exc:
                    st.error(f"Ошибка загрузки: {exc}")
                else:
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
