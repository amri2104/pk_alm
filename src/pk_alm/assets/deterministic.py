"""Deterministic Stage-1 asset baseline.

This module intentionally stays small: it calibrates opening assets from the
liability proxy and rolls assets forward with one deterministic return rate
and annual net cashflows.
"""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass

import pandas as pd

from pk_alm.analytics.cashflows import validate_annual_cashflow_dataframe
from pk_alm.bvg.valuation import validate_valuation_dataframe

ASSET_SNAPSHOT_COLUMNS = (
    "projection_year",
    "opening_asset_value",
    "investment_return",
    "net_cashflow",
    "closing_asset_value",
    "annual_return_rate",
    "currency",
)

_ASSET_IDENTITY_TOLERANCE = 1e-5
_MONETARY_FIELDS = (
    "opening_asset_value",
    "investment_return",
    "net_cashflow",
    "closing_asset_value",
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_non_bool_int(
    value: object, name: str, *, min_value: int | None = None
) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, int):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")
    if min_value is not None and value < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {value}")
    return value


def _validate_non_bool_real(
    value: object,
    name: str,
    *,
    min_value: float | None = None,
    allow_equal_min: bool = True,
) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be numeric, got {type(value).__name__}")
    fval = float(value)
    if math.isnan(fval):
        raise ValueError(f"{name} must not be NaN")
    if min_value is not None:
        if allow_equal_min:
            if fval < min_value:
                raise ValueError(f"{name} must be >= {min_value}, got {fval}")
        else:
            if fval <= min_value:
                raise ValueError(f"{name} must be > {min_value}, got {fval}")
    return fval


def _validate_non_empty_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _coerce_integer_like(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real):
        fval = float(value)
        if math.isnan(fval):
            raise ValueError(f"{name} must not be NaN")
        if not fval.is_integer():
            raise ValueError(f"{name} must be integer-like, got {value!r}")
        return int(fval)
    raise TypeError(f"{name} must be integer-like, got {type(value).__name__}")


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeterministicAssetSnapshot:
    """One deterministic asset roll-forward snapshot."""

    projection_year: int
    opening_asset_value: float
    investment_return: float
    net_cashflow: float
    closing_asset_value: float
    annual_return_rate: float
    currency: str = "CHF"

    def __post_init__(self) -> None:
        _validate_non_bool_int(self.projection_year, "projection_year", min_value=0)

        for fname in _MONETARY_FIELDS:
            _validate_non_bool_real(getattr(self, fname), fname)

        _validate_non_bool_real(
            self.annual_return_rate,
            "annual_return_rate",
            min_value=-1.0,
            allow_equal_min=False,
        )
        _validate_non_empty_string(self.currency, "currency")

        expected = (
            self.opening_asset_value + self.investment_return + self.net_cashflow
        )
        if not math.isclose(
            self.closing_asset_value,
            expected,
            abs_tol=_ASSET_IDENTITY_TOLERANCE,
        ):
            raise ValueError(
                "closing_asset_value must equal opening_asset_value + "
                "investment_return + net_cashflow "
                f"(expected {expected}, got {self.closing_asset_value})"
            )

    def to_dict(self) -> dict[str, object]:
        return {col: getattr(self, col) for col in ASSET_SNAPSHOT_COLUMNS}


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


def calibrate_initial_assets(
    initial_total_stage1_liability: float,
    target_funding_ratio: float,
) -> float:
    """Calibrate opening assets from liabilities and a decimal funding ratio."""
    liability = _validate_non_bool_real(
        initial_total_stage1_liability,
        "initial_total_stage1_liability",
        min_value=0.0,
        allow_equal_min=False,
    )
    ratio = _validate_non_bool_real(
        target_funding_ratio,
        "target_funding_ratio",
        min_value=0.0,
        allow_equal_min=False,
    )
    return liability * ratio


def project_assets_one_year(
    opening_asset_value: float,
    net_cashflow: float,
    annual_return_rate: float,
    *,
    projection_year: int,
    currency: str = "CHF",
) -> DeterministicAssetSnapshot:
    """Roll assets forward for one year with year-end cashflow timing."""
    opening = _validate_non_bool_real(opening_asset_value, "opening_asset_value")
    net = _validate_non_bool_real(net_cashflow, "net_cashflow")
    rate = _validate_non_bool_real(
        annual_return_rate,
        "annual_return_rate",
        min_value=-1.0,
        allow_equal_min=False,
    )
    year = _validate_non_bool_int(projection_year, "projection_year", min_value=1)
    cur = _validate_non_empty_string(currency, "currency")

    investment_return = opening * rate
    closing = opening + investment_return + net

    return DeterministicAssetSnapshot(
        projection_year=year,
        opening_asset_value=opening,
        investment_return=investment_return,
        net_cashflow=net,
        closing_asset_value=closing,
        annual_return_rate=rate,
        currency=cur,
    )


def asset_snapshots_to_dataframe(snapshots: list | tuple) -> pd.DataFrame:
    """Convert deterministic asset snapshots to the canonical DataFrame."""
    if not isinstance(snapshots, (list, tuple)):
        raise TypeError(
            f"snapshots must be list or tuple, got {type(snapshots).__name__}"
        )
    for i, snapshot in enumerate(snapshots):
        if not isinstance(snapshot, DeterministicAssetSnapshot):
            raise TypeError(
                f"snapshots[{i}] must be DeterministicAssetSnapshot, "
                f"got {type(snapshot).__name__}"
            )
    return pd.DataFrame(
        [snapshot.to_dict() for snapshot in snapshots],
        columns=list(ASSET_SNAPSHOT_COLUMNS),
    )


# ---------------------------------------------------------------------------
# DataFrame validation
# ---------------------------------------------------------------------------


def validate_asset_dataframe(df: pd.DataFrame) -> bool:
    """Validate the deterministic asset snapshot DataFrame."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError(
            f"df must be a pandas DataFrame, got {type(df).__name__}"
        )

    missing = [c for c in ASSET_SNAPSHOT_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")

    if list(df.columns) != list(ASSET_SNAPSHOT_COLUMNS):
        raise ValueError(
            f"columns must be in order {list(ASSET_SNAPSHOT_COLUMNS)}, "
            f"got {list(df.columns)}"
        )

    if df.empty:
        return True

    if df[list(ASSET_SNAPSHOT_COLUMNS)].isna().any().any():
        raise ValueError("required columns must not contain NaN/None/NaT/pd.NA")

    for idx, row in df.iterrows():
        prefix = f"row {idx}"

        projection_year = _coerce_integer_like(
            row["projection_year"], f"{prefix}: projection_year"
        )
        _validate_non_bool_int(
            projection_year, f"{prefix}: projection_year", min_value=0
        )

        for fname in _MONETARY_FIELDS:
            _validate_non_bool_real(row[fname], f"{prefix}: {fname}")

        _validate_non_bool_real(
            row["annual_return_rate"],
            f"{prefix}: annual_return_rate",
            min_value=-1.0,
            allow_equal_min=False,
        )

        _validate_non_empty_string(row["currency"], f"{prefix}: currency")

        expected = (
            row["opening_asset_value"]
            + row["investment_return"]
            + row["net_cashflow"]
        )
        if not math.isclose(
            row["closing_asset_value"],
            expected,
            abs_tol=_ASSET_IDENTITY_TOLERANCE,
        ):
            raise ValueError(
                f"{prefix}: closing_asset_value must equal opening_asset_value + "
                f"investment_return + net_cashflow "
                f"(expected {expected}, got {row['closing_asset_value']})"
            )

    return True


# ---------------------------------------------------------------------------
# Trajectory
# ---------------------------------------------------------------------------


def build_deterministic_asset_trajectory(
    valuation_snapshots: pd.DataFrame,
    annual_cashflows: pd.DataFrame,
    *,
    target_funding_ratio: float,
    annual_return_rate: float,
    start_year: int = 2026,
    currency: str = "CHF",
) -> pd.DataFrame:
    """Build a deterministic asset trajectory aligned to valuation snapshots."""
    if not isinstance(valuation_snapshots, pd.DataFrame):
        raise TypeError(
            f"valuation_snapshots must be a pandas DataFrame, "
            f"got {type(valuation_snapshots).__name__}"
        )
    validate_valuation_dataframe(valuation_snapshots)

    if not isinstance(annual_cashflows, pd.DataFrame):
        raise TypeError(
            f"annual_cashflows must be a pandas DataFrame, "
            f"got {type(annual_cashflows).__name__}"
        )
    validate_annual_cashflow_dataframe(annual_cashflows)

    target_ratio = _validate_non_bool_real(
        target_funding_ratio,
        "target_funding_ratio",
        min_value=0.0,
        allow_equal_min=False,
    )
    return_rate = _validate_non_bool_real(
        annual_return_rate,
        "annual_return_rate",
        min_value=-1.0,
        allow_equal_min=False,
    )
    first_year = _validate_non_bool_int(start_year, "start_year", min_value=0)
    cur = _validate_non_empty_string(currency, "currency")

    if valuation_snapshots.empty:
        raise ValueError("valuation_snapshots must have at least one row")

    first_projection_year = _coerce_integer_like(
        valuation_snapshots.iloc[0]["projection_year"],
        "valuation_snapshots.iloc[0]: projection_year",
    )
    if first_projection_year != 0:
        raise ValueError(
            "the first valuation snapshot must have projection_year == 0, "
            f"got {first_projection_year}"
        )

    expected_cashflow_rows = len(valuation_snapshots) - 1
    if len(annual_cashflows) != expected_cashflow_rows:
        raise ValueError(
            "annual_cashflows must have len(valuation_snapshots) - 1 rows "
            f"({expected_cashflow_rows}), got {len(annual_cashflows)}"
        )

    if annual_cashflows.empty and len(valuation_snapshots) != 1:
        raise ValueError(
            "annual_cashflows may be empty only when valuation_snapshots has one row"
        )

    if not annual_cashflows.empty:
        years = [
            _coerce_integer_like(y, "annual_cashflows.reporting_year")
            for y in annual_cashflows["reporting_year"]
        ]
        if len(set(years)) != len(years):
            raise ValueError("annual_cashflows reporting_year values must be unique")
        if years != sorted(years):
            raise ValueError(
                "annual_cashflows reporting_year values must be sorted ascending"
            )
        contiguous_years = list(range(years[0], years[0] + len(years)))
        if years != contiguous_years:
            raise ValueError(
                "annual_cashflows reporting_year values must be contiguous"
            )
        expected_years = list(
            range(first_year, first_year + len(valuation_snapshots) - 1)
        )
        if years != expected_years:
            raise ValueError(
                "annual_cashflows reporting_year values must exactly match "
                f"{expected_years}, got {years}"
            )

    initial_liability = float(
        valuation_snapshots.iloc[0]["total_stage1_liability"]
    )
    initial_assets = calibrate_initial_assets(initial_liability, target_ratio)

    snapshots: list[DeterministicAssetSnapshot] = [
        DeterministicAssetSnapshot(
            projection_year=0,
            opening_asset_value=initial_assets,
            investment_return=0.0,
            net_cashflow=0.0,
            closing_asset_value=initial_assets,
            annual_return_rate=0.0,
            currency=cur,
        )
    ]

    previous_closing = initial_assets
    for i in range(1, len(valuation_snapshots)):
        projection_year = _coerce_integer_like(
            valuation_snapshots.iloc[i]["projection_year"],
            f"valuation_snapshots.iloc[{i}]: projection_year",
        )
        target_reporting_year = first_year + projection_year - 1
        matching = annual_cashflows.loc[
            annual_cashflows["reporting_year"] == target_reporting_year,
            "net_cashflow",
        ]
        if len(matching) != 1:
            raise ValueError(
                "expected exactly one annual cashflow row for reporting_year "
                f"{target_reporting_year}, got {len(matching)}"
            )

        snapshot = project_assets_one_year(
            previous_closing,
            float(matching.iloc[0]),
            return_rate,
            projection_year=projection_year,
            currency=cur,
        )
        snapshots.append(snapshot)
        previous_closing = snapshot.closing_asset_value

    df = asset_snapshots_to_dataframe(snapshots)
    validate_asset_dataframe(df)
    return df
