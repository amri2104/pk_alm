"""Table helpers for the dashboard export tab."""

from __future__ import annotations

import pandas as pd


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"df must be a pandas DataFrame, got {type(df).__name__}")
    return df.to_csv(index=False).encode("utf-8")


def analytics_export_frames(analytics: object) -> dict[str, pd.DataFrame]:
    return {
        "kpi_summary": analytics.kpi_summary,
        "annual_cashflows": analytics.annual_cashflows,
        "funding_ratio_trajectory": analytics.funding_ratio_trajectory,
        "combined_cashflows": analytics.combined_cashflows,
        "validation_report": analytics.validation_report,
    }

