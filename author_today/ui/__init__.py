"""Веб-интерфейс Streamlit: страницы, компоненты, кэш отчётов."""

__all__ = ["StreamlitApp"]


def __getattr__(name: str):
    if name == "StreamlitApp":
        from author_today.ui.app import StreamlitApp

        return StreamlitApp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
