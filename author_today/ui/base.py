"""Базовые абстракции UI (ISP + LSP: страницы взаимозаменяемы через Page)."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Page(ABC):
    """Экран приложения. Новый экран — новый класс, без правок App (OCP)."""

    @property
    @abstractmethod
    def title(self) -> str:
        """Подпись вкладки."""

    @abstractmethod
    def render(self) -> None:
        """Отрисовать содержимое вкладки."""
