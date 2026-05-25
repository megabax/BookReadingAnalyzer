"""Анализ продаж из reclan.csv (отдельный источник данных)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_sales_csv(path: Path, encoding: str = "cp1251") -> pd.DataFrame:
    return pd.read_csv(path, encoding=encoding, sep=";")
