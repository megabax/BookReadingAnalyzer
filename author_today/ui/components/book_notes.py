"""CRUD заметок к книге (дата + текст)."""

from __future__ import annotations

from datetime import date

import streamlit as st

from author_today.errors import AuthorTodayError
from author_today.services.notes import (
    MAX_NOTE_BODY_LEN,
    create_book_note,
    delete_book_note,
    list_book_notes,
    update_book_note,
)
from config.settings import Settings


class BookNotesPanel:
    """Управление заметками выбранной книги (SRP: без графиков)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def render(self, book_id: int, *, key_prefix: str = "notes") -> None:
        if not self._settings.has_mssql():
            return

        with st.expander("Заметки по книге", expanded=False):
            st.caption(
                "Дата + текст, привязка к book_id. На тренде дочитывания заметки "
                "в выбранном периоде подсвечиваются на графике."
            )
            try:
                notes = list_book_notes(self._settings, book_id)
            except AuthorTodayError as exc:
                st.error(str(exc))
                return

            if notes:
                st.dataframe(
                    [
                        {
                            "id": n.note_id,
                            "дата": n.note_date,
                            "текст": n.body,
                        }
                        for n in notes
                    ],
                    hide_index=True,
                    width="stretch",
                )
            else:
                st.info("Заметок пока нет.")

            st.markdown("**Добавить**")
            add_cols = st.columns([1, 3, 1])
            with add_cols[0]:
                new_date = st.date_input(
                    "Дата",
                    value=date.today(),
                    key=f"{key_prefix}_add_date_{book_id}",
                )
            with add_cols[1]:
                new_body = st.text_input(
                    "Текст",
                    value="",
                    max_chars=MAX_NOTE_BODY_LEN,
                    key=f"{key_prefix}_add_body_{book_id}",
                    placeholder="например: реклама, новая обложка…",
                )
            with add_cols[2]:
                st.write("")  # align button
                if st.button("Добавить", key=f"{key_prefix}_add_btn_{book_id}"):
                    try:
                        create_book_note(self._settings, book_id, new_date, new_body)
                    except AuthorTodayError as exc:
                        st.error(str(exc))
                    else:
                        st.success("Заметка добавлена.")
                        st.rerun()

            if not notes:
                return

            st.markdown("**Изменить / удалить**")
            by_id = {n.note_id: n for n in notes}
            selected_id = st.selectbox(
                "Заметка",
                options=list(by_id.keys()),
                format_func=lambda nid: (
                    f"#{nid} · {by_id[nid].note_date} · {by_id[nid].body[:60]}"
                ),
                key=f"{key_prefix}_edit_select_{book_id}",
            )
            current = by_id[int(selected_id)]
            edit_cols = st.columns([1, 3])
            with edit_cols[0]:
                edit_date = st.date_input(
                    "Дата",
                    value=current.note_date,
                    key=f"{key_prefix}_edit_date_{book_id}_{current.note_id}",
                )
            with edit_cols[1]:
                edit_body = st.text_area(
                    "Текст",
                    value=current.body,
                    max_chars=MAX_NOTE_BODY_LEN,
                    key=f"{key_prefix}_edit_body_{book_id}_{current.note_id}",
                    height=80,
                )
            b1, b2 = st.columns(2)
            with b1:
                if st.button("Сохранить", key=f"{key_prefix}_save_{book_id}"):
                    try:
                        update_book_note(
                            self._settings,
                            book_id,
                            current.note_id,
                            note_date=edit_date,
                            body=edit_body,
                        )
                    except AuthorTodayError as exc:
                        st.error(str(exc))
                    else:
                        st.success("Заметка обновлена.")
                        st.rerun()
            with b2:
                confirm = st.checkbox(
                    "Подтверждаю удаление",
                    key=f"{key_prefix}_del_confirm_{book_id}_{current.note_id}",
                )
                if st.button(
                    "Удалить",
                    type="primary",
                    disabled=not confirm,
                    key=f"{key_prefix}_del_btn_{book_id}",
                ):
                    try:
                        delete_book_note(self._settings, book_id, current.note_id)
                    except AuthorTodayError as exc:
                        st.error(str(exc))
                    else:
                        st.success("Заметка удалена.")
                        st.rerun()
