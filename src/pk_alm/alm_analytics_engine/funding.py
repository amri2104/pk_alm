"""Funding-ratio analytics for the deterministic Stage-1 baseline."""

from __future__ import annotations

import math
import numbers

import pandas as pd

from pk_alm.actus_asset_engine.deterministic import validate_asset_dataframe
from pk_alm.bvg_liability_engine.pension_logic.valuation import validate_valuation_dataframe

FUNDING_RATIO_COLUMNS = (
    "projection_year",
    "asset_value",
    "total_stage1_liability",
    "funding_ratio",
    "funding_ratio_percent",
    "currency",
)

_FUNDING_TOLERANCE = 1e-5


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
# Pure functions
# ---------------------------------------------------------------------------


def calculate_funding_ratio(
    asset_value: float,
    total_stage1_liability: float,
) -> float:
    """Return asset_value / total_stage1_liability."""
    assets = _validate_non_bool_real(asset_value, "asset_value")
    liability = _validate_non_bool_real(
        total_stage1_liability,
        "total_stage1_liability",
        min_value=0.0,
        allow_equal_min=False,
    )
    return assets / liability


def build_funding_ratio_trajectory(
    asset_snapshots: pd.DataFrame,
    valuation_snapshots: pd.DataFrame,
    *,
    currency: str = "CHF",
) -> pd.DataFrame:
    """Build a funding-ratio trajectory from asset and liability snapshots."""
    if not isinstance(asset_snapshots, pd.DataFrame):
        raise TypeError(
            f"asset_snapshots must be a pandas DataFrame, "
            f"got {type(asset_snapshots).__name__}"
        )
    validate_asset_dataframe(asset_snapshots)

    if not isinstance(valuation_snapshots, pd.DataFrame):
        raise TypeError(
            f"valuation_snapshots must be a pandas DataFrame, "
            f"got {type(valuation_snapshots).__name__}"
        )
    validate_valuation_dataframe(valuation_snapshots)

    cur = _validate_non_empty_string(currency, "currency")

    if len(asset_snapshots) != len(valuation_snapshots):
        raise ValueError(
            "asset_snapshots and valuation_snapshots must have the same number "
            f"of rows ({len(asset_snapshots)} != {len(valuation_snapshots)})"
        )

    asset_years = [
        _coerce_integer_like(y, "asset_snapshots.projection_year")
        for y in asset_snapshots["projection_year"]
    ]
    valuation_years = [
        _coerce_integer_like(y, "valuation_snapshots.projection_year")
        for y in valuation_snapshots["projection_year"]
    ]
    if asset_years != valuation_years:
        raise ValueError(
            "asset_snapshots and valuation_snapshots must have identical "
            f"projection_year sequences ({asset_years} != {valuation_years})"
        )

    rows: list[dict[str, object]] = []
    for i in range(len(asset_snapshots)):
        projection_year = asset_years[i]
        asset_value = float(asset_snapshots.iloc[i]["closing_asset_value"])
        liability = float(valuation_snapshots.iloc[i]["total_stage1_liability"])
        funding_ratio = calculate_funding_ratio(asset_value, liability)

        rows.append(
            {
                "projection_year": projection_year,
                "asset_value": asset_value,
                "total_stage1_liability": liability,
                "funding_ratio": funding_ratio,
                "funding_ratio_percent": funding_ratio * 100,
                "currency": cur,
            }
        )

    df = pd.DataFrame(rows, columns=list(FUNDING_RATIO_COLUMNS))
    validate_funding_ratio_dataframe(df)
    return df


# ---------------------------------------------------------------------------
# DataFrame validation
# ---------------------------------------------------------------------------


def validate_funding_ratio_dataframe(df: pd.DataFrame) -> bool:
    """Validate the funding-ratio trajectory DataFrame."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError(
            f"df must be a pandas DataFrame, got {type(df).__name__}"
        )

    missing = [c for c in FUNDING_RATIO_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")

    if list(df.columns) != list(FUNDING_RATIO_COLUMNS):
        raise ValueError(
            f"columns must be in order {list(FUNDING_RATIO_COLUMNS)}, "
            f"got {list(df.columns)}"
        )

    if df.empty:
        return True

    if df[list(FUNDING_RATIO_COLUMNS)].isna().any().any():
        raise ValueError("required columns must not contain NaN/None/NaT/pd.NA")

    for idx, row in df.iterrows():
        prefix = f"row {idx}"

        projection_year = _coerce_integer_like(
            row["projection_year"], f"{prefix}: projection_year"
        )
        _validate_non_bool_int(
            projection_year, f"{prefix}: projection_year", min_value=0
        )

        asset_value = _validate_non_bool_real(
            row["asset_value"], f"{prefix}: asset_value"
        )
        liability = _validate_non_bool_real(
            row["total_stage1_liability"],
            f"{prefix}: total_stage1_liability",
            min_value=0.0,
            allow_equal_min=False,
        )
        funding_ratio = _validate_non_bool_real(
            row["funding_ratio"], f"{prefix}: funding_ratio"
        )
        funding_ratio_percent = _validate_non_bool_real(
            row["funding_ratio_percent"], f"{prefix}: funding_ratio_percent"
        )
        _validate_non_empty_string(row["currency"], f"{prefix}: currency")

        expected_ratio = asset_value / liability
        if not math.isclose(
            funding_ratio, expected_ratio, abs_tol=_FUNDING_TOLERANCE
        ):
            raise ValueError(
                f"{prefix}: funding_ratio must equal asset_value / "
                f"total_stage1_liability "
                f"(expected {expected_ratio}, got {funding_ratio})"
            )

        expected_percent = funding_ratio * 100
        if not math.isclose(
            funding_ratio_percent,
            expected_percent,
            abs_tol=_FUNDING_TOLERANCE,
        ):
            raise ValueError(
                f"{prefix}: funding_ratio_percent must equal funding_ratio * 100 "
                f"(expected {expected_percent}, got {funding_ratio_percent})"
            )

    return True
