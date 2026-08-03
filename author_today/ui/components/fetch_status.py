"""Глобальный баннер статуса фоновой загрузки Selenium."""

from __future__ import annotations

from datetime import timedelta

import streamlit as st

from author_today.services.fetch import FetchJob, FetchProgress, get_job, list_active_jobs
from author_today.ui.cache import ReportCache

JOB_STATE_KEY = "fetch_job_id"
RESULT_STATE_KEY = "fetch_last_result"


def bind_job(job: FetchJob) -> None:
    st.session_state[JOB_STATE_KEY] = job.job_id


def clear_job_binding() -> None:
    st.session_state.pop(JOB_STATE_KEY, None)


def resolve_job() -> FetchJob | None:
    job_id = st.session_state.get(JOB_STATE_KEY)
    if job_id:
        job = get_job(job_id)
        if job is not None:
            return job
        clear_job_binding()
    active = list_active_jobs()
    if active:
        bind_job(active[0])
        return active[0]
    return None


def _render_progress_body(progress: FetchProgress) -> None:
    period = ""
    if progress.period_start and progress.period_end:
        period = f" · {progress.period_start} — {progress.period_end}"
    st.caption(
        f"book_id={progress.book_id}{period} · порции {progress.chunk_label}"
        + (
            f" · метрики: {', '.join(progress.value_types)}"
            if progress.value_types
            else ""
        )
        + (f" · сейчас: {progress.value_type}" if progress.value_type else "")
    )
    st.progress(progress.fraction)
    st.write(progress.stage)


@st.fragment(run_every=timedelta(seconds=2))
def render_fetch_status_banner(*, report_cache: ReportCache | None = None) -> None:
    """Показывать на всех вкладках; обновляется раз в 2 с, пока job активен."""
    job = resolve_job()
    if job is None:
        st.session_state.pop("_fetch_prev_status", None)
        return

    progress = job.snapshot()
    if progress.status == "idle":
        return

    prev_status = st.session_state.get("_fetch_prev_status")
    if progress.status != prev_status:
        st.session_state["_fetch_prev_status"] = progress.status
        # Полный rerun при смене статуса — иначе вкладка «Загрузка» остаётся со старым UI.
        if progress.status in ("awaiting_code", "done", "error", "cancelled") and prev_status in (
            "running",
            "awaiting_code",
            None,
            "idle",
        ):
            st.rerun()

    if progress.status == "running":
        st.info("Идёт загрузка с author.today (можно переключать вкладки).")
        _render_progress_body(progress)
        if st.button("Отменить загрузку", key="fetch_banner_cancel"):
            job.cancel()
            st.rerun()
        return

    if progress.status == "awaiting_code":
        hint = progress.hint or "код подтверждения"
        st.warning(
            f"Загрузка приостановлена: нужен **{hint}**. "
            "Введите код ниже и нажмите «Продолжить»."
        )
        _render_progress_body(progress)
        code = st.text_input(
            "Код подтверждения устройства / 2FA",
            value="",
            key="fetch_banner_device_code",
            help="Код будет введён в сессию Chrome программно.",
        )
        col_ok, col_cancel = st.columns(2)
        with col_ok:
            continue_clicked = st.button(
                "Продолжить",
                type="primary",
                key="fetch_banner_continue",
            )
        with col_cancel:
            cancel_clicked = st.button(
                "Отменить загрузку",
                key="fetch_banner_cancel_code",
            )

        if cancel_clicked:
            job.cancel()
            st.rerun()
        if continue_clicked:
            text = (code or "").strip()
            if not text:
                st.error("Введите код подтверждения.")
                return
            job.submit_code(text)
            st.toast("Код отправлен, загрузка продолжается…")
            st.rerun()
        return

    if progress.status == "done":
        if progress.result is not None:
            st.session_state[RESULT_STATE_KEY] = progress.result
            if report_cache is not None:
                report_cache.clear_all()
        st.success(
            progress.stage
            or "Загрузка завершена. Данные в MS SQL — можно строить отчёты."
        )
        if progress.result is not None:
            st.caption(
                f"Глав: {progress.result.chapter_count}, "
                f"дней: {progress.result.day_count}, "
                f"порций: {progress.result.monthly_chunks}"
            )
        if st.button("Скрыть", key="fetch_banner_dismiss_done"):
            job.dismiss()
            clear_job_binding()
            st.rerun()
        return

    if progress.status == "error":
        st.error(progress.error or progress.stage or "Ошибка загрузки")
        if st.button("Скрыть", key="fetch_banner_dismiss_error"):
            job.dismiss()
            clear_job_binding()
            st.rerun()
        return

    if progress.status == "cancelled":
        st.warning("Загрузка отменена.")
        if st.button("Скрыть", key="fetch_banner_dismiss_cancelled"):
            job.dismiss()
            clear_job_binding()
            st.rerun()
