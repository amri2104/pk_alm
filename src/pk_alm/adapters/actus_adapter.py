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


# ---------------------------------------------------------------------------
# AAL event normalization
# ---------------------------------------------------------------------------

_AAL_KEY_ALIASES: dict[str, tuple[str, ...]] = {
    "contract_id": ("contract_id", "contractID", "contractId"),
    "event_date": ("event_date", "eventDate", "time"),
    "event_type": ("event_type", "eventType", "type"),
    "payoff": ("payoff",),
    "nominal_value": ("nominal_value", "nominalValue"),
    "currency": ("currency",),
}

_AAL_REQUIRED_CANONICAL_KEYS = ("contract_id", "event_date", "event_type", "payoff")


def _normalize_aal_event(
    event: object,
    *,
    default_currency: str,
) -> dict:
    """Map an AAL-style event dict to the canonical adapter dict shape."""
    if not isinstance(event, dict):
        raise TypeError(
            f"AAL event must be a dict, got {type(event).__name__}"
        )

    normalized: dict[str, object] = {}
    for canonical, aliases in _AAL_KEY_ALIASES.items():
        for alias in aliases:
            if alias in event:
                normalized[canonical] = event[alias]
                break

    missing = [k for k in _AAL_REQUIRED_CANONICAL_KEYS if k not in normalized]
    if missing:
        raise ValueError(f"missing required AAL event keys: {missing}")

    normalized.setdefault("nominal_value", 0.0)
    normalized.setdefault("currency", default_currency)
    return normalized


def aal_events_to_cashflow_dataframe(
    events: object,
    *,
    default_currency: str = "CHF",
) -> pd.DataFrame:
    """Convert AAL-generated event output into a schema-valid cashflow DataFrame.

    Accepts:
      - a single ``dict``,
      - a ``list`` or ``tuple`` of dicts,
      - a ``pandas.DataFrame`` whose columns are AAL-style event keys,
      - a wrapper object exposing an ``events_df`` ``DataFrame`` attribute.

    The returned DataFrame always has ``source == "ACTUS"`` on every row
    (the source value is set by the existing ACTUS adapter, not by AAL).
    Unknown shapes raise ``TypeError``; missing required keys raise
    ``ValueError``.
    """
    if not isinstance(default_currency, str) or not default_currency.strip():
        raise ValueError("default_currency must be a non-empty string")

    extracted: object = events
    if (
        not isinstance(extracted, (dict, list, tuple, pd.DataFrame))
        and hasattr(extracted, "events_df")
    ):
        extracted = extracted.events_df

    if isinstance(extracted, pd.DataFrame):
        records = extracted.to_dict(orient="records")
    elif isinstance(extracted, dict):
        records = [extracted]
    elif isinstance(extracted, (list, tuple)):
        records = list(extracted)
    else:
        raise TypeError(
            f"events must be dict, list, tuple, DataFrame, or an object with "
            f"an 'events_df' DataFrame attribute, got {type(extracted).__name__}"
        )

    normalized = [
        _normalize_aal_event(event, default_currency=default_currency)
        for event in records
    ]
    return actus_events_to_cashflow_dataframe(normalized)
