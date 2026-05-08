"""Plot-ready tables derived from ALM Analytics results."""

from __future__ import annotations

import pandas as pd

from pk_alm.alm_analytics_engine.alm_kpis import (
    build_cashflow_by_source_plot_table as _build_cashflow_by_source_from_cashflows,
    build_net_cashflow_plot_table as _build_net_cashflow_from_annual,
)
from pk_alm.alm_analytics_engine.funding import validate_funding_ratio_dataframe

FUNDING_RATIO_PLOT_COLUMNS = (
    "projection_year",
    "funding_ratio_percent",
    "target_funding_ratio_percent",
)


def build_cashflow_by_source_plot_table(result: object) -> pd.DataFrame:
    from pk_alm.alm_analytics_engine.analytics_result import ALMAnalyticsResult

    if isinstance(result, ALMAnalyticsResult):
        return result.cashflow_by_source_plot_table.copy(deep=True)
    return _build_cashflow_by_source_from_cashflows(result)


def build_net_cashflow_plot_table(result: object) -> pd.DataFrame:
    from pk_alm.alm_analytics_engine.analytics_result import ALMAnalyticsResult

    if isinstance(result, ALMAnalyticsResult):
        return result.net_cashflow_plot_table.copy(deep=True)
    return _build_net_cashflow_from_annual(result)


def build_funding_ratio_plot_table(
    result: object,
    *,
    target_funding_ratio: float | None = None,
) -> pd.DataFrame:
    from pk_alm.alm_analytics_engine.analytics_result import ALMAnalyticsResult

    if isinstance(result, ALMAnalyticsResult):
        return result.funding_ratio_plot_table.copy(deep=True)
    if target_funding_ratio is None:
        raise TypeError(
            "target_funding_ratio is required when building from a "
            "funding-ratio trajectory DataFrame"
        )
    funding_ratio_trajectory = result
    if not isinstance(funding_ratio_trajectory, pd.DataFrame):
        raise TypeError(
            "result must be ALMAnalyticsResult or a funding-ratio trajectory "
            f"DataFrame, got {type(result).__name__}"
        )
    validate_funding_ratio_dataframe(funding_ratio_trajectory)
    if funding_ratio_trajectory.empty:
        return pd.DataFrame(columns=list(FUNDING_RATIO_PLOT_COLUMNS))
    frame = funding_ratio_trajectory.loc[
        :, ["projection_year", "funding_ratio_percent"]
    ].copy(deep=True)
    frame["target_funding_ratio_percent"] = float(target_funding_ratio) * 100.0
    return frame.loc[:, list(FUNDING_RATIO_PLOT_COLUMNS)]
