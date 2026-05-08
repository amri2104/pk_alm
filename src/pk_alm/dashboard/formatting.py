"""Small display-formatting helpers for the dashboard."""

from __future__ import annotations

import math

import pandas as pd


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def format_percent(value: object) -> str:
    if _is_missing(value):
        return "-"
    numeric = float(value)
    if math.isnan(numeric):
        return "-"
    return f"{numeric:,.2f}%"


def format_chf(value: object) -> str:
    if _is_missing(value):
        return "-"
    numeric = float(value)
    if math.isnan(numeric):
        return "-"
    return f"CHF {numeric:,.0f}"


def format_int(value: object) -> str:
    if _is_missing(value):
        return "-"
    numeric = float(value)
    if math.isnan(numeric):
        return "-"
    return f"{int(round(numeric)):,}"


def safe_scalar(
    df: pd.DataFrame,
    column: str,
    default: object | None = None,
) -> object | None:
    if not isinstance(df, pd.DataFrame) or df.empty or column not in df.columns:
        return default
    value = df.iloc[0][column]
    return default if _is_missing(value) else value

