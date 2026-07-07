#!/usr/bin/env python
"""
Точка входа веб-интерфейса AutorToday.

Запуск из корня проекта:
    pip install -r requirements.txt -r requirements-ui.txt
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
import altair as alt

from author_today.analyze.funnel import (
    FunnelStep,
    default_funnel_csv_path,
    save_funnel_csv,
)
from author_today.services.books import BookOption, load_book_catalog, load_book_data_info
from author_today.services.fetch import fetch_reads_for_period
from author_today.services.reports import load_funnel_steps
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


def _mssql_cache_key(settings: Settings) -> str:
    if settings.mssql_server and settings.mssql_database:
        return f"{settings.mssql_server}|{settings.mssql_database}"
    return "mssql"


@st.cache_data(ttl=600, show_spinner=False)
def _cached_funnel_steps(
    _cache_key: str,
    book_id: int,
    period_start: date,
    period_end: date,
    skip_book_page: bool,
    baseline_chapter_order: int | None,
) -> list[FunnelStep]:
    return load_funnel_steps(
        settings,
        book_id,
        period_start,
        period_end,
        skip_book_page=skip_book_page,
        baseline_chapter_order=baseline_chapter_order,
    )


def _funnel_pct_column_label(baseline_chapter_order: int | None) -> str:
    if baseline_chapter_order is None:
        return "% от 1-й"
    return f"% от гл.{baseline_chapter_order}"


def _funnel_steps_dataframe(
    steps: list[FunnelStep],
    *,
    baseline_chapter_order: int | None,
) -> pd.DataFrame:
    pct_col = _funnel_pct_column_label(baseline_chapter_order)
    return pd.DataFrame(
        [
            {
                "№": step.step_num,
                "chapter_order": step.site_chapter_order,
                "Глава": step.chapter_name,
                "Просмотры": step.total_views,
                pct_col: step.pct_of_first,
                "% от пред.": step.pct_of_previous,
                "Падение": step.drop_from_previous,
            }
            for step in steps
        ]
    )


def _funnel_csv_bytes(
    steps: list[FunnelStep],
    *,
    baseline_chapter_order: int | None,
) -> bytes:
    with tempfile.TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "funnel.csv"
        save_funnel_csv(steps, path, baseline_chapter_order=baseline_chapter_order)
        return path.read_bytes()


def _render_funnel_chart(steps: list[FunnelStep], *, y_title: str) -> None:
    """График % от базы; Altair — st.line_chart ломается на «% от 1-й» в имени колонки."""
    chart_df = pd.DataFrame(
        {
            "step": [s.step_num for s in steps],
            "pct": [float(s.pct_of_first) for s in steps],
            "chapter": [s.chapter_name for s in steps],
        }
    )
    chart = (
        alt.Chart(chart_df)
        .mark_line(point=True)
        .encode(
            x=alt.X("step:Q", title="№ шага воронки"),
            y=alt.Y("pct:Q", title=y_title, scale=alt.Scale(zero=False)),
            tooltip=[
                alt.Tooltip("step:Q", title="№"),
                alt.Tooltip("chapter:N", title="Глава"),
                alt.Tooltip("pct:Q", title=y_title, format=".1f"),
            ],
        )
        .properties(height=420)
    )
    st.altair_chart(chart, use_container_width=True)


def pick_book_id(
    catalog: list[BookOption],
    settings: Settings,
    *,
    key_prefix: str,
) -> int:
    """Выбор book_id: каталог или ручной ввод."""
    book_mode = st.radio(
        "Книга",
        options=["Из списка", "Новый book_id"],
        horizontal=True,
        key=f"{key_prefix}_book_mode",
    )

    if book_mode == "Из списка":
        if catalog:
            labels = [book.label for book in catalog]
            default_label = next(
                (book.label for book in catalog if book.book_id == settings.book_id),
                labels[0],
            )
            picked = st.selectbox(
                "Выберите книгу",
                options=labels,
                index=labels.index(default_label),
                key=f"{key_prefix}_book_select",
            )
            return _resolve_book_id_from_catalog(catalog, picked)

        st.info("Каталог пуст. Укажите book_id вручную.")
        return int(
            st.number_input(
                "book_id",
                min_value=1,
                value=settings.book_id,
                step=1,
                key=f"{key_prefix}_book_id_empty_catalog",
            )
        )

    return int(
        st.number_input(
            "book_id (workId в URL author.today)",
            min_value=1,
            value=settings.book_id,
            step=1,
            key=f"{key_prefix}_book_id_manual",
        )
    )


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
    st.caption(
        "Сумма просмотров по главам за период из MS SQL; "
        "% от базовой главы и % от предыдущей."
    )

    if not settings.has_mssql():
        st.warning("Настройте MS SQL в `.env` — отчёт строится из `chapter_reads`.")
    else:
        funnel_catalog = load_book_catalog(settings)
        funnel_book_id = pick_book_id(funnel_catalog, settings, key_prefix="funnel")

        col_start, col_end = st.columns(2)
        with col_start:
            funnel_start = st.date_input(
                "Начало периода",
                value=settings.default_period_start,
                key="funnel_period_start",
            )
        with col_end:
            funnel_end = st.date_input(
                "Конец периода",
                value=settings.default_period_end,
                key="funnel_period_end",
            )

        with st.expander("Параметры воронки", expanded=False):
            skip_book_page = st.checkbox(
                "Исключить «Страница книги»",
                value=True,
                key="funnel_skip_book_page",
                help="Как флаг --skip-book-page в CLI.",
            )
            use_custom_base = st.checkbox(
                "База 100% — не первая глава воронки",
                value=False,
                key="funnel_use_custom_base",
            )
            baseline_chapter_order: int | None = None
            if use_custom_base:
                baseline_chapter_order = int(
                    st.number_input(
                        "chapter_order базовой главы (как на сайте)",
                        min_value=1,
                        value=2,
                        step=1,
                        key="funnel_base_order",
                        help="Аналог --base-order в scripts/report_funnel.py",
                    )
                )

        build_funnel = st.button("Построить воронку", type="primary", key="funnel_build")
        if st.button("Сбросить кэш отчёта", key="funnel_clear_cache"):
            _cached_funnel_steps.clear()
            st.toast("Кэш воронки очищен")

        if build_funnel:
            if funnel_start > funnel_end:
                st.error("Начало периода не может быть позже конца.")
            else:
                try:
                    with st.spinner("Загрузка данных из MS SQL…"):
                        steps = _cached_funnel_steps(
                            _mssql_cache_key(settings),
                            funnel_book_id,
                            funnel_start,
                            funnel_end,
                            skip_book_page,
                            baseline_chapter_order,
                        )
                except ValueError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"Ошибка построения воронки: {exc}")
                else:
                    if not steps:
                        st.warning(
                            "Нет данных за выбранный период. "
                            "Загрузите статистику на вкладке «Загрузка»."
                        )
                    else:
                        pct_col = _funnel_pct_column_label(baseline_chapter_order)
                        baseline_step = (
                            next(
                                (
                                    s
                                    for s in steps
                                    if s.site_chapter_order == baseline_chapter_order
                                ),
                                None,
                            )
                            if baseline_chapter_order is not None
                            else steps[0]
                        )
                        st.success(
                            f"book_id={funnel_book_id}, {funnel_start} — {funnel_end} · "
                            f"шагов: {len(steps)}"
                        )
                        m1, m2, m3 = st.columns(3)
                        m1.metric("Шагов воронки", len(steps))
                        if baseline_step:
                            m2.metric(
                                "База (просмотры)",
                                baseline_step.total_views,
                                help=baseline_step.chapter_name,
                            )
                        m3.metric(
                            "Последняя глава, % от базы",
                            f"{steps[-1].pct_of_first:.1f}%",
                        )

                        st.markdown(f"**{pct_col}** по шагам воронки")
                        _render_funnel_chart(steps, y_title=pct_col)

                        table_df = _funnel_steps_dataframe(
                            steps,
                            baseline_chapter_order=baseline_chapter_order,
                        )
                        st.dataframe(
                            table_df,
                            hide_index=True,
                            width="stretch",
                            column_config={
                                "% от пред.": st.column_config.NumberColumn(format="%.1f"),
                                pct_col: st.column_config.NumberColumn(format="%.1f"),
                            },
                        )

                        csv_name = default_funnel_csv_path(
                            funnel_book_id,
                            funnel_start,
                            funnel_end,
                        ).name
                        st.download_button(
                            "Скачать CSV",
                            data=_funnel_csv_bytes(
                                steps,
                                baseline_chapter_order=baseline_chapter_order,
                            ),
                            file_name=csv_name,
                            mime="text/csv",
                            key="funnel_download_csv",
                        )

                        st.caption(
                            "Повторные загрузки того же периода суммируются в БД. "
                            "При дублях run'ов воронка может быть завышена — см. "
                            "`scripts/delete_runs.py` и `scripts/check_load_gaps.py`."
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
    selected_book_id = pick_book_id(catalog, settings, key_prefix="fetch")

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
