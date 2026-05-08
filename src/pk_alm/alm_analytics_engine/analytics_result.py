"""Canonical result object for the stateless ALM Analytics Engine."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from pk_alm.alm_analytics_engine.analytics_input import ALMAnalyticsInput
from pk_alm.alm_analytics_engine.alm_kpis import (
    CASHFLOW_BY_SOURCE_PLOT_COLUMNS,
    NET_CASHFLOW_PLOT_COLUMNS,
    validate_alm_kpi_summary_dataframe,
)
from pk_alm.alm_analytics_engine.cashflows import (
    validate_annual_cashflow_dataframe,
)
from pk_alm.alm_analytics_engine.funding import validate_funding_ratio_dataframe
from pk_alm.alm_analytics_engine.funding_summary import (
    validate_funding_summary_dataframe,
)
from pk_alm.alm_analytics_engine.reporting.plot_tables import (
    FUNDING_RATIO_PLOT_COLUMNS,
)
from pk_alm.alm_analytics_engine.validation import (
    validate_alm_validation_report_dataframe,
)
from pk_alm.cashflows.schema import validate_cashflow_dataframe


def _validate_exact_columns(
    df: pd.DataFrame,
    *,
    name: str,
    expected_columns: tuple[str, ...],
) -> None:
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"{name} must be a pandas DataFrame")
    if list(df.columns) != list(expected_columns):
        raise ValueError(
            f"{name} columns must be {list(expected_columns)}, "
            f"got {list(df.columns)}"
        )


@dataclass(frozen=True)
class ALMAnalyticsResult:
    """Deterministic ALM analytics outputs plus optional stochastic tables."""

    inputs: ALMAnalyticsInput
    combined_cashflows: pd.DataFrame
    annual_cashflows: pd.DataFrame
    funding_ratio_trajectory: pd.DataFrame
    funding_summary: pd.DataFrame
    kpi_summary: pd.DataFrame
    cashflow_by_source_plot_table: pd.DataFrame
    net_cashflow_plot_table: pd.DataFrame
    funding_ratio_plot_table: pd.DataFrame
    validation_report: pd.DataFrame
    stochastic_summary: pd.DataFrame | None = None
    stochastic_percentiles: pd.DataFrame | None = None
    liquidity_inflection_distribution: pd.DataFrame | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.inputs, ALMAnalyticsInput):
            raise TypeError("inputs must be ALMAnalyticsInput")
        validate_cashflow_dataframe(self.combined_cashflows)
        validate_annual_cashflow_dataframe(self.annual_cashflows)
        validate_funding_ratio_dataframe(self.funding_ratio_trajectory)
        validate_funding_summary_dataframe(self.funding_summary)
        validate_alm_kpi_summary_dataframe(self.kpi_summary)
        _validate_exact_columns(
            self.cashflow_by_source_plot_table,
            name="cashflow_by_source_plot_table",
            expected_columns=CASHFLOW_BY_SOURCE_PLOT_COLUMNS,
        )
        _validate_exact_columns(
            self.net_cashflow_plot_table,
            name="net_cashflow_plot_table",
            expected_columns=NET_CASHFLOW_PLOT_COLUMNS,
        )
        _validate_exact_columns(
            self.funding_ratio_plot_table,
            name="funding_ratio_plot_table",
            expected_columns=FUNDING_RATIO_PLOT_COLUMNS,
        )
        validate_alm_validation_report_dataframe(self.validation_report)
        for name in (
            "stochastic_summary",
            "stochastic_percentiles",
            "liquidity_inflection_distribution",
        ):
            value = getattr(self, name)
            if value is not None and not isinstance(value, pd.DataFrame):
                raise TypeError(f"{name} must be DataFrame or None")
