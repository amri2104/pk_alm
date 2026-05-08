"""Canonical input object for the stateless ALM Analytics Engine."""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass

import pandas as pd

from pk_alm.actus_asset_engine.deterministic import validate_asset_dataframe
from pk_alm.bvg_liability_engine.pension_logic.valuation import (
    validate_valuation_dataframe,
)
from pk_alm.cashflows.schema import validate_cashflow_dataframe


def _validate_non_empty_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _validate_positive_real(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be numeric, got {type(value).__name__}")
    result = float(value)
    if math.isnan(result):
        raise ValueError(f"{name} must not be NaN")
    if result <= 0.0:
        raise ValueError(f"{name} must be > 0")
    return result


def _currencies(df: pd.DataFrame) -> set[str]:
    if df.empty or "currency" not in df.columns:
        return set()
    return set(str(value) for value in df["currency"].unique().tolist())


def _validate_currency_set(
    df: pd.DataFrame,
    *,
    name: str,
    expected_currency: str,
    allow_empty: bool,
) -> None:
    if df.empty:
        if allow_empty:
            return
        raise ValueError(f"{name} must not be empty")
    observed = _currencies(df)
    if observed != {expected_currency}:
        raise ValueError(
            f"{name} currency must be {expected_currency!r}, got {sorted(observed)}"
        )


def _projection_years(df: pd.DataFrame, name: str) -> tuple[int, ...]:
    if df.empty:
        raise ValueError(f"{name} must not be empty")
    return tuple(int(value) for value in df["projection_year"].tolist())


@dataclass(frozen=True)
class ALMAnalyticsInput:
    """Precomputed engine outputs consumed by the ALM Analytics Engine."""

    bvg_cashflows: pd.DataFrame
    asset_cashflows: pd.DataFrame
    asset_snapshots: pd.DataFrame
    valuation_snapshots: pd.DataFrame
    scenario_name: str = "base_case"
    target_funding_ratio: float = 1.0
    currency: str = "CHF"

    def __post_init__(self) -> None:
        scenario_name = _validate_non_empty_string(
            self.scenario_name, "scenario_name"
        )
        currency = _validate_non_empty_string(self.currency, "currency")
        target = _validate_positive_real(
            self.target_funding_ratio, "target_funding_ratio"
        )

        for name in (
            "bvg_cashflows",
            "asset_cashflows",
            "asset_snapshots",
            "valuation_snapshots",
        ):
            if not isinstance(getattr(self, name), pd.DataFrame):
                raise TypeError(f"{name} must be a pandas DataFrame")

        validate_cashflow_dataframe(self.bvg_cashflows)
        validate_cashflow_dataframe(self.asset_cashflows)
        validate_asset_dataframe(self.asset_snapshots)
        validate_valuation_dataframe(self.valuation_snapshots)

        _validate_currency_set(
            self.bvg_cashflows,
            name="bvg_cashflows",
            expected_currency=currency,
            allow_empty=False,
        )
        _validate_currency_set(
            self.asset_cashflows,
            name="asset_cashflows",
            expected_currency=currency,
            allow_empty=True,
        )
        _validate_currency_set(
            self.asset_snapshots,
            name="asset_snapshots",
            expected_currency=currency,
            allow_empty=False,
        )
        _validate_currency_set(
            self.valuation_snapshots,
            name="valuation_snapshots",
            expected_currency=currency,
            allow_empty=False,
        )

        asset_years = _projection_years(self.asset_snapshots, "asset_snapshots")
        valuation_years = _projection_years(
            self.valuation_snapshots, "valuation_snapshots"
        )
        if asset_years != valuation_years:
            raise ValueError(
                "asset_snapshots.projection_year must match "
                "valuation_snapshots.projection_year "
                f"({asset_years} != {valuation_years})"
            )

        object.__setattr__(self, "scenario_name", scenario_name)
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "target_funding_ratio", target)
