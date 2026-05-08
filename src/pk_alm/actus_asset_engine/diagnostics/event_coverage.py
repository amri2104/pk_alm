"""Coverage diagnostics for AAL event output."""

from __future__ import annotations

import pandas as pd

from pk_alm.actus_asset_engine.contract_config import AALContractConfig
from pk_alm.actus_asset_engine.simulation_settings import AALSimulationSettings
from pk_alm.cashflows.schema import validate_cashflow_dataframe

EVENT_COVERAGE_COLUMNS = (
    "contractId",
    "contractType",
    "expected_event_types",
    "observed_event_types",
    "missing_event_types",
    "status",
    "warning",
)

_EXPECTED_TYPES_BY_CONTRACT = {
    "PAM": ("IP", "MD"),
    "STK": ("TD",),
    "CSH": (),
}


def _observed_types(cashflows: pd.DataFrame, contract_id: str) -> tuple[str, ...]:
    if cashflows.empty:
        return ()
    observed = cashflows.loc[cashflows["contractId"].eq(contract_id), "type"]
    return tuple(sorted(set(str(value) for value in observed)))


def build_event_coverage_report(
    contracts: tuple[AALContractConfig, ...],
    cashflows: pd.DataFrame,
    settings: AALSimulationSettings,
) -> pd.DataFrame:
    validate_cashflow_dataframe(cashflows)
    rows: list[dict[str, object]] = []
    for config in contracts:
        expected = _EXPECTED_TYPES_BY_CONTRACT.get(config.contract_type, ())
        observed = _observed_types(cashflows, config.contract_id)
        missing = tuple(event for event in expected if event not in observed)
        warnings: list[str] = []
        if settings.mode == "exploratory" and missing:
            warnings.append("Expected event type missing in exploratory mode")
        if config.contract_type == "STK" and "cycleOfDividend" in config.terms:
            warnings.append(
                "Public AAL reference server may omit STK dividend events"
            )
        if config.contract_type == "CSH":
            warnings.append(
                "Public AAL reference server emits no temporal CSH events"
            )
        rows.append(
            {
                "contractId": config.contract_id,
                "contractType": config.contract_type,
                "expected_event_types": ",".join(expected),
                "observed_event_types": ",".join(observed),
                "missing_event_types": ",".join(missing),
                "status": "warning" if missing or warnings else "ok",
                "warning": "; ".join(warnings),
            }
        )
    return pd.DataFrame(rows, columns=list(EVENT_COVERAGE_COLUMNS))
