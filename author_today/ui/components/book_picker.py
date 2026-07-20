"""Выбор книги из каталога или ручной ввод book_id."""

from __future__ import annotations

import streamlit as st

from author_today.services.books import BookOption
from config.settings import Settings


class BookPicker:
    """Виджет выбора book_id; не знает про отчёты и загрузку (SRP)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def pick(self, catalog: list[BookOption], *, key_prefix: str) -> int:
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
                    (book.label for book in catalog if book.book_id == self._settings.book_id),
                    labels[0],
                )
                picked = st.selectbox(
                    "Выберите книгу",
                    options=labels,
                    index=labels.index(default_label),
                    key=f"{key_prefix}_book_select",
                )
                return self._resolve_book_id(catalog, picked)

            st.info("Каталог пуст. Укажите book_id вручную.")
            return int(
                st.number_input(
                    "book_id",
                    min_value=1,
                    value=self._settings.book_id,
                    step=1,
                    key=f"{key_prefix}_book_id_empty_catalog",
                )
            )

        return int(
            st.number_input(
                "book_id (workId в URL author.today)",
                min_value=1,
                value=self._settings.book_id,
                step=1,
                key=f"{key_prefix}_book_id_manual",
            )
        )

    @staticmethod
    def _resolve_book_id(catalog: list[BookOption], label: str) -> int:
        for book in catalog:
            if book.label == label:
                return book.book_id
        raise ValueError(f"Неизвестная книга в списке: {label}")
