"""Canonical cashflow schema shared by liability and asset engines.

Source values distinguish where an event originated:
- ``"BVG"``: liability-side BVG cashflows.
- ``"ACTUS"``: live server-emitted AAL/ACTUS asset events.
- ``"ACTUS_PROXY"``: asset events synthesized by the engine for cashflows
  the live ACTUS server does not emit.
- ``"MANUAL"``: manually supplied/imported cashflows.
"""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass

import pandas as pd

CASHFLOW_COLUMNS = (
    "contractId",
    "time",
    "type",
    "payoff",
    "nominalValue",
    "currency",
    "source",
)

VALID_SOURCES = ("BVG", "ACTUS", "ACTUS_PROXY", "MANUAL")


def _validate_numeric(value: object, field_name: str, *, allow_negative: bool) -> None:
    """Validate that value is a real number (not bool, not NaN), with sign rule."""
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must not be bool")
    if not isinstance(value, numbers.Real):
        raise ValueError(
            f"{field_name} must be numeric, got {type(value).__name__}"
        )
    fval = float(value)
    if math.isnan(fval):
        raise ValueError(f"{field_name} must not be NaN")
    if not allow_negative and fval < 0:
        raise ValueError(f"{field_name} must be >= 0, got {fval}")


def _validate_nonempty_string(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True)
class CashflowRecord:
    """A single cashflow event in the shared schema.

    Sign convention (from pension fund perspective):
      payoff > 0  : cash inflow to the fund (e.g. contribution, coupon)
      payoff < 0  : cash outflow from the fund (e.g. pension payment)
      payoff == 0 : state update only (e.g. PV roll-forward)
    """

    contractId: str
    time: object
    type: str
    payoff: float
    nominalValue: float = 0.0
    currency: str = "CHF"
    source: str = "BVG"

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.contractId, "contractId")

        if self.time is None:
            raise ValueError("time must not be None")
        try:
            ts = pd.Timestamp(self.time)
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"time could not be converted to pd.Timestamp: {self.time!r}"
            ) from e
        if pd.isna(ts):
            raise ValueError(
                f"time could not be converted to pd.Timestamp: {self.time!r}"
            )
        object.__setattr__(self, "time", ts)

        _validate_nonempty_string(self.type, "type")
        _validate_numeric(self.payoff, "payoff", allow_negative=True)
        _validate_numeric(self.nominalValue, "nominalValue", allow_negative=False)
        _validate_nonempty_string(self.currency, "currency")

        if self.source not in VALID_SOURCES:
            raise ValueError(
                f"source must be one of {VALID_SOURCES}, got {self.source!r}"
            )

    def to_dict(self) -> dict[str, object]:
        """Return record fields keyed in CASHFLOW_COLUMNS order."""
        return {
            "contractId": self.contractId,
            "time": self.time,
            "type": self.type,
            "payoff": self.payoff,
            "nominalValue": self.nominalValue,
            "currency": self.currency,
            "source": self.source,
        }


def cashflow_records_to_dataframe(records: list | tuple) -> pd.DataFrame:
    """Convert a list/tuple of CashflowRecord into a DataFrame with the canonical schema."""
    if not isinstance(records, (list, tuple)):
        raise TypeError(
            f"records must be list or tuple, got {type(records).__name__}"
        )
    for i, r in enumerate(records):
        if not isinstance(r, CashflowRecord):
            raise TypeError(
                f"records[{i}] must be CashflowRecord, got {type(r).__name__}"
            )
    return pd.DataFrame(
        [r.to_dict() for r in records], columns=list(CASHFLOW_COLUMNS)
    )


def validate_cashflow_dataframe(df: pd.DataFrame) -> bool:
    """Validate that df conforms to the shared cashflow schema.

    Returns True if all checks pass; otherwise raises ValueError or TypeError.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(
            f"df must be a pandas DataFrame, got {type(df).__name__}"
        )

    missing = [c for c in CASHFLOW_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")

    if list(df.columns) != list(CASHFLOW_COLUMNS):
        raise ValueError(
            f"columns must be in order {list(CASHFLOW_COLUMNS)}, "
            f"got {list(df.columns)}"
        )

    for idx, row in df.iterrows():
        prefix = f"row {idx}"

        cid = row["contractId"]
        if not isinstance(cid, str) or not cid.strip():
            raise ValueError(f"{prefix}: contractId must be a non-empty string")

        t = row["time"]
        if pd.isna(t):
            raise ValueError(f"{prefix}: time must not be NaT/None/NaN")
        try:
            pd.Timestamp(t)
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"{prefix}: time could not be converted to pd.Timestamp: {t!r}"
            ) from e

        typ = row["type"]
        if not isinstance(typ, str) or not typ.strip():
            raise ValueError(f"{prefix}: type must be a non-empty string")

        _validate_numeric(row["payoff"], f"{prefix}: payoff", allow_negative=True)
        _validate_numeric(
            row["nominalValue"], f"{prefix}: nominalValue", allow_negative=False
        )

        cur = row["currency"]
        if not isinstance(cur, str) or not cur.strip():
            raise ValueError(f"{prefix}: currency must be a non-empty string")

        src = row["source"]
        if src not in VALID_SOURCES:
            raise ValueError(
                f"{prefix}: source must be one of {VALID_SOURCES}, got {src!r}"
            )

    return True
