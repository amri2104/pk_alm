"""Minimal adapter boundary for future ACTUS/AAL asset events.

This module is the seam where simplified ACTUS/AAL-style asset events will
later enter the project's canonical cashflow schema. It does **not** import
or call the Awesome ACTUS Library (AAL), does not depend on any ACTUS
service, and does not implement any contract logic.

Its only responsibility is to map a small, explicit set of ACTUS-style
event-dictionary keys into existing `CashflowRecord` objects so that
asset-side cashflows can flow through the same validators, analytics, and
funding-ratio layers as BVG cashflows.

Full AAL integration (ContractModel, Portfolio, RiskFactor, ActusService,
CashFlowStream) is deferred to a later sprint. Until then the contract here
is intentionally narrow: dict in, schema-valid `CashflowRecord` out.
"""

from __future__ import annotations

import copy

import pandas as pd

from pk_alm.cashflows.schema import (
    CashflowRecord,
    cashflow_records_to_dataframe,
    validate_cashflow_dataframe,
)

ACTUS_SOURCE = "ACTUS"

_REQUIRED_KEYS = ("contract_id", "event_date", "event_type", "payoff")


def actus_event_to_cashflow_record(event: dict) -> CashflowRecord:
    """Convert one ACTUS-style event dictionary into a CashflowRecord.

    Required keys: ``contract_id``, ``event_date``, ``event_type``, ``payoff``.
    Optional keys: ``nominal_value`` (default ``0.0``),
    ``currency`` (default ``"CHF"``).
    The ``source`` field on the resulting record is always ``ACTUS_SOURCE``.

    Detailed value validation (non-empty strings, valid timestamp, numeric /
    non-NaN payoff and nominal value, non-negative nominal value, valid
    source) is delegated to :class:`CashflowRecord`. The input dictionary is
    not mutated; a defensive deep copy is taken before reading.
    """
    if not isinstance(event, dict):
        raise TypeError(f"event must be a dict, got {type(event).__name__}")

    missing = [key for key in _REQUIRED_KEYS if key not in event]
    if missing:
        raise ValueError(f"missing required ACTUS event keys: {missing}")

    safe = copy.deepcopy(event)

    return CashflowRecord(
        contractId=safe["contract_id"],
        time=safe["event_date"],
        type=safe["event_type"],
        payoff=safe["payoff"],
        nominalValue=safe.get("nominal_value", 0.0),
        currency=safe.get("currency", "CHF"),
        source=ACTUS_SOURCE,
    )


def actus_events_to_cashflow_records(
    events: list | tuple,
) -> tuple[CashflowRecord, ...]:
    """Convert a list/tuple of ACTUS-style event dicts to CashflowRecords.

    Preserves input order. Empty input returns an empty tuple. Each item must
    be a dict; any non-dict item raises ``TypeError`` with its index. Inputs
    are not mutated.
    """
    if not isinstance(events, (list, tuple)):
        raise TypeError(
            f"events must be list or tuple, got {type(events).__name__}"
        )
    for i, item in enumerate(events):
        if not isinstance(item, dict):
            raise TypeError(
                f"events[{i}] must be dict, got {type(item).__name__}"
            )
    return tuple(actus_event_to_cashflow_record(event) for event in events)


def actus_events_to_cashflow_dataframe(events: list | tuple) -> pd.DataFrame:
    """Convert ACTUS-style events into a schema-valid cashflow DataFrame.

    Empty input returns an empty schema-valid DataFrame with the canonical
    cashflow columns. The returned DataFrame always passes
    :func:`validate_cashflow_dataframe`.
    """
    records = actus_events_to_cashflow_records(events)
    df = cashflow_records_to_dataframe(list(records))
    validate_cashflow_dataframe(df)
    return df
