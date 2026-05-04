"""Funding-ratio summary analytics for the deterministic Stage-1 baseline."""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass

import pandas as pd

from pk_alm.alm_analytics_engine.funding import validate_funding_ratio_dataframe

FUNDING_SUMMARY_COLUMNS = (
    "start_projection_year",
    "end_projection_year",
    "initial_funding_ratio_percent",
    "final_funding_ratio_percent",
    "minimum_funding_ratio_percent",
    "minimum_funding_ratio_projection_year",
    "maximum_funding_ratio_percent",
    "maximum_funding_ratio_projection_year",
    "target_funding_ratio_percent",
    "years_below_100_percent",
    "years_below_target_percent",
    "ever_underfunded",
    "final_underfunded",
    "currency",
)

_SUMMARY_TOLERANCE = 1e-5
_PERCENT_FIELDS = (
    "initial_funding_ratio_percent",
    "final_funding_ratio_percent",
    "minimum_funding_ratio_percent",
    "maximum_funding_ratio_percent",
    "target_funding_ratio_percent",
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


def _coerce_bool(value: object, name: str) -> bool:
    """Coerce Python bool, numpy bool, or 'True'/'False' strings to Python bool.

    Strings are accepted to support CSV roundtrip via pandas, which writes bool
    columns as the strings 'True' and 'False'.
    """
    if isinstance(value, bool):
        return value
    if pd.api.types.is_bool(value):
        return bool(value)
    if isinstance(value, str):
        s = value.strip()
        if s == "True":
            return True
        if s == "False":
            return False
    raise TypeError(f"{name} must be bool, got {type(value).__name__}")


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
# Summary container
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FundingRatioSummary:
    """Compact summary of one funding-ratio trajectory."""

    start_projection_year: int
    end_projection_year: int
    initial_funding_ratio_percent: float
    final_funding_ratio_percent: float
    minimum_funding_ratio_percent: float
    minimum_funding_ratio_projection_year: int
    maximum_funding_ratio_percent: float
    maximum_funding_ratio_projection_year: int
    target_funding_ratio_percent: float
    years_below_100_percent: int
    years_below_target_percent: int
    ever_underfunded: bool
    final_underfunded: bool
    currency: str = "CHF"

    def __post_init__(self) -> None:
        start = _validate_non_bool_int(
            self.start_projection_year,
            "start_projection_year",
            min_value=0,
        )
        end = _validate_non_bool_int(
            self.end_projection_year,
            "end_projection_year",
            min_value=0,
        )
        if end < start:
            raise ValueError(
                "end_projection_year must be >= start_projection_year "
                f"({end} < {start})"
            )

        minimum_year = _validate_non_bool_int(
            self.minimum_funding_ratio_projection_year,
            "minimum_funding_ratio_projection_year",
            min_value=0,
        )
        maximum_year = _validate_non_bool_int(
            self.maximum_funding_ratio_projection_year,
            "maximum_funding_ratio_projection_year",
            min_value=0,
        )
        if not start <= minimum_year <= end:
            raise ValueError(
                "minimum_funding_ratio_projection_year must lie between start and end "
                f"projection years ({start} <= {minimum_year} <= {end})"
            )
        if not start <= maximum_year <= end:
            raise ValueError(
                "maximum_funding_ratio_projection_year must lie between start and end "
                f"projection years ({start} <= {maximum_year} <= {end})"
            )

        for fname in _PERCENT_FIELDS:
            _validate_non_bool_real(getattr(self, fname), fname)
        _validate_non_bool_real(
            self.target_funding_ratio_percent,
            "target_funding_ratio_percent",
            min_value=0.0,
            allow_equal_min=False,
        )

        year_count = end - start + 1
        below_100 = _validate_non_bool_int(
            self.years_below_100_percent,
            "years_below_100_percent",
            min_value=0,
        )
        below_target = _validate_non_bool_int(
            self.years_below_target_percent,
            "years_below_target_percent",
            min_value=0,
        )
        if below_100 > year_count:
            raise ValueError(
                "years_below_100_percent must be <= number of years "
                f"({below_100} > {year_count})"
            )
        if below_target > year_count:
            raise ValueError(
                "years_below_target_percent must be <= number of years "
                f"({below_target} > {year_count})"
            )

        if not isinstance(self.ever_underfunded, bool):
            raise TypeError(
                f"ever_underfunded must be bool, "
                f"got {type(self.ever_underfunded).__name__}"
            )
        if not isinstance(self.final_underfunded, bool):
            raise TypeError(
                f"final_underfunded must be bool, "
                f"got {type(self.final_underfunded).__name__}"
            )

        _validate_non_empty_string(self.currency, "currency")

    def to_dict(self) -> dict[str, object]:
        return {col: getattr(self, col) for col in FUNDING_SUMMARY_COLUMNS}


# ---------------------------------------------------------------------------
# Summary logic
# ---------------------------------------------------------------------------


def summarize_funding_ratio(
    funding_ratio_trajectory: pd.DataFrame,
    *,
    target_funding_ratio: float,
    currency: str = "CHF",
) -> FundingRatioSummary:
    """Summarize a validated funding-ratio trajectory."""
    if not isinstance(funding_ratio_trajectory, pd.DataFrame):
        raise TypeError(
            f"funding_ratio_trajectory must be a pandas DataFrame, "
            f"got {type(funding_ratio_trajectory).__name__}"
        )
    validate_funding_ratio_dataframe(funding_ratio_trajectory)
    if funding_ratio_trajectory.empty:
        raise ValueError("funding_ratio_trajectory must not be empty")

    target_ratio = _validate_non_bool_real(
        target_funding_ratio,
        "target_funding_ratio",
        min_value=0.0,
        allow_equal_min=False,
    )
    cur = _validate_non_empty_string(currency, "currency")

    work = funding_ratio_trajectory.copy(deep=True)
    years = [
        _coerce_integer_like(y, "funding_ratio_trajectory.projection_year")
        for y in work["projection_year"]
    ]
    if len(set(years)) != len(years):
        raise ValueError(
            "funding_ratio_trajectory projection_year values must be unique"
        )
    if years != sorted(years):
        raise ValueError(
            "funding_ratio_trajectory projection_year values must be sorted ascending"
        )
    expected_years = list(range(years[0], years[0] + len(years)))
    if years != expected_years:
        raise ValueError(
            "funding_ratio_trajectory projection_year values must be contiguous"
        )

    percentages = [
        _validate_non_bool_real(
            value,
            "funding_ratio_trajectory.funding_ratio_percent",
        )
        for value in work["funding_ratio_percent"]
    ]

    min_percent = percentages[0]
    min_year = years[0]
    max_percent = percentages[0]
    max_year = years[0]
    for year, percent in zip(years, percentages):
        if percent < min_percent:
            min_percent = percent
            min_year = year
        if percent > max_percent:
            max_percent = percent
            max_year = year

    target_percent = target_ratio * 100
    years_below_100 = sum(
        1 for percent in percentages if percent < 100.0 - _SUMMARY_TOLERANCE
    )
    years_below_target = sum(
        1
        for percent in percentages
        if percent < target_percent - _SUMMARY_TOLERANCE
    )
    final_percent = percentages[-1]

    return FundingRatioSummary(
        start_projection_year=years[0],
        end_projection_year=years[-1],
        initial_funding_ratio_percent=percentages[0],
        final_funding_ratio_percent=final_percent,
        minimum_funding_ratio_percent=min_percent,
        minimum_funding_ratio_projection_year=min_year,
        maximum_funding_ratio_percent=max_percent,
        maximum_funding_ratio_projection_year=max_year,
        target_funding_ratio_percent=target_percent,
        years_below_100_percent=years_below_100,
        years_below_target_percent=years_below_target,
        ever_underfunded=years_below_100 > 0,
        final_underfunded=final_percent < 100.0 - _SUMMARY_TOLERANCE,
        currency=cur,
    )


def funding_summary_to_dataframe(
    summary: FundingRatioSummary | list | tuple,
) -> pd.DataFrame:
    """Convert one or more FundingRatioSummary objects to a DataFrame."""
    if isinstance(summary, FundingRatioSummary):
        summaries = [summary]
    elif isinstance(summary, (list, tuple)):
        summaries = list(summary)
    else:
        raise TypeError(
            "summary must be FundingRatioSummary, list, or tuple, "
            f"got {type(summary).__name__}"
        )

    for i, item in enumerate(summaries):
        if not isinstance(item, FundingRatioSummary):
            raise TypeError(
                f"summary[{i}] must be FundingRatioSummary, "
                f"got {type(item).__name__}"
            )

    return pd.DataFrame(
        [item.to_dict() for item in summaries],
        columns=list(FUNDING_SUMMARY_COLUMNS),
    )


def validate_funding_summary_dataframe(df: pd.DataFrame) -> bool:
    """Validate a funding-ratio summary DataFrame."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError(
            f"df must be a pandas DataFrame, got {type(df).__name__}"
        )

    missing = [c for c in FUNDING_SUMMARY_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")

    if list(df.columns) != list(FUNDING_SUMMARY_COLUMNS):
        raise ValueError(
            f"columns must be in order {list(FUNDING_SUMMARY_COLUMNS)}, "
            f"got {list(df.columns)}"
        )

    if df.empty:
        return True

    if df[list(FUNDING_SUMMARY_COLUMNS)].isna().any().any():
        raise ValueError("required columns must not contain NaN/None/NaT/pd.NA")

    for _, row in df.iterrows():
        FundingRatioSummary(
            start_projection_year=_coerce_integer_like(
                row["start_projection_year"], "start_projection_year"
            ),
            end_projection_year=_coerce_integer_like(
                row["end_projection_year"], "end_projection_year"
            ),
            initial_funding_ratio_percent=row["initial_funding_ratio_percent"],
            final_funding_ratio_percent=row["final_funding_ratio_percent"],
            minimum_funding_ratio_percent=row["minimum_funding_ratio_percent"],
            minimum_funding_ratio_projection_year=_coerce_integer_like(
                row["minimum_funding_ratio_projection_year"],
                "minimum_funding_ratio_projection_year",
            ),
            maximum_funding_ratio_percent=row["maximum_funding_ratio_percent"],
            maximum_funding_ratio_projection_year=_coerce_integer_like(
                row["maximum_funding_ratio_projection_year"],
                "maximum_funding_ratio_projection_year",
            ),
            target_funding_ratio_percent=row["target_funding_ratio_percent"],
            years_below_100_percent=_coerce_integer_like(
                row["years_below_100_percent"], "years_below_100_percent"
            ),
            years_below_target_percent=_coerce_integer_like(
                row["years_below_target_percent"], "years_below_target_percent"
            ),
            ever_underfunded=_coerce_bool(
                row["ever_underfunded"], "ever_underfunded"
            ),
            final_underfunded=_coerce_bool(
                row["final_underfunded"], "final_underfunded"
            ),
            currency=row["currency"],
        )

    return True
