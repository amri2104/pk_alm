"""Date filtering and cut-off validation for ACTUS/AAL cashflows."""

from __future__ import annotations

import pandas as pd

from pk_alm.actus_asset_engine.contract_config import AALContractConfig
from pk_alm.actus_asset_engine.simulation_settings import AALSimulationSettings
from pk_alm.cashflows.schema import CASHFLOW_COLUMNS, validate_cashflow_dataframe

_SORT_COLUMNS = ["time", "contractId", "type", "source"]


def _empty_cashflow_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=list(CASHFLOW_COLUMNS))


def filter_cashflows_for_settings(
    cashflows: pd.DataFrame,
    settings: AALSimulationSettings,
) -> pd.DataFrame:
    """Apply the engine's simulation cut-off rules and stable sort order."""
    validate_cashflow_dataframe(cashflows)
    if cashflows.empty:
        return _empty_cashflow_frame()

    filtered = cashflows.copy()
    times = pd.to_datetime(filtered["time"])
    mask = times.le(settings.event_end_date)
    if settings.cashflow_cutoff_mode == "from_status_date":
        mask &= times.ge(settings.event_start_date)
    filtered = filtered.loc[mask, list(CASHFLOW_COLUMNS)].copy()
    if filtered.empty:
        return _empty_cashflow_frame()
    filtered["time"] = pd.to_datetime(filtered["time"])
    return filtered.sort_values(_SORT_COLUMNS, ignore_index=True)


def validate_historical_initial_exchange_cutoff(
    contracts: tuple[AALContractConfig, ...],
    cashflows: pd.DataFrame,
    settings: AALSimulationSettings,
) -> None:
    """Ensure historical contract inception events do not leak into ALM output."""
    if settings.cashflow_cutoff_mode != "from_status_date" or cashflows.empty:
        return
    times = pd.to_datetime(cashflows["time"])
    for contract in contracts:
        initial_exchange = contract.term_timestamp("initialExchangeDate")
        status_date = contract.term_timestamp("statusDate")
        if initial_exchange is None or status_date is None:
            continue
        if initial_exchange >= status_date:
            continue
        leaked = cashflows.loc[
            cashflows["contractId"].eq(contract.contract_id)
            & times.lt(settings.event_start_date)
        ]
        if not leaked.empty:
            raise ValueError(
                "historical initialExchangeDate leaked into filtered ACTUS "
                f"cashflows for {contract.contract_id!r}"
            )
