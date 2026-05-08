"""Event summaries for ACTUS/AAL cashflow output."""

from __future__ import annotations

import pandas as pd

from pk_alm.cashflows.schema import validate_cashflow_dataframe

EVENT_SUMMARY_COLUMNS = (
    "contractId",
    "type",
    "reporting_year",
    "event_count",
    "total_payoff",
)


def build_event_summary(cashflows: pd.DataFrame) -> pd.DataFrame:
    validate_cashflow_dataframe(cashflows)
    if cashflows.empty:
        return pd.DataFrame(columns=list(EVENT_SUMMARY_COLUMNS))

    frame = cashflows.copy()
    frame["reporting_year"] = pd.to_datetime(frame["time"]).dt.year.astype(int)
    grouped = (
        frame.groupby(["contractId", "type", "reporting_year"], as_index=False)
        .agg(event_count=("payoff", "size"), total_payoff=("payoff", "sum"))
        .sort_values(["reporting_year", "contractId", "type"], ignore_index=True)
    )
    return grouped.loc[:, list(EVENT_SUMMARY_COLUMNS)]
