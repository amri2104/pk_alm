"""Minimal time-grid helpers for future monthly simulations.

This module defines a small standalone time-grid abstraction for later
monthly cashflow work. The current deterministic Stage-1 baseline remains
annual; this module does not alter the BVG engine, valuation, funding ratio,
or scenario pipeline. It prepares a safe path for future monthly PR/RP
cashflow generation while keeping annual discretisation as the reference
baseline.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import numbers

import pandas as pd

SUPPORTED_FREQUENCIES = ("ANNUAL", "MONTHLY")
PERIODS_PER_YEAR = {"ANNUAL": 1, "MONTHLY": 12}
TIME_GRID_COLUMNS = (
    "frequency",
    "step_index",
    "projection_year",
    "reporting_year",
    "period_in_year",
    "event_date",
)


def _validate_non_bool_int(
    value: object,
    name: str,
    *,
    min_value: int | None = None,
) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, numbers.Integral):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")
    result = int(value)
    if min_value is not None and result < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {result}")
    return result


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
    result = float(value)
    if math.isnan(result):
        raise ValueError(f"{name} must not be NaN")
    if min_value is not None:
        if allow_equal_min and result < min_value:
            raise ValueError(f"{name} must be >= {min_value}, got {result}")
        if not allow_equal_min and result <= min_value:
            raise ValueError(f"{name} must be > {min_value}, got {result}")
    return result


def _coerce_timestamp(value: object, name: str) -> pd.Timestamp:
    if value is None:
        raise ValueError(f"{name} must not be None")
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} could not be converted to pd.Timestamp") from exc
    if pd.isna(timestamp):
        raise ValueError(f"{name} must not be NaT/NaN")
    return timestamp


def normalize_frequency(frequency: str) -> str:
    """Return a normalized supported frequency."""
    if not isinstance(frequency, str):
        raise TypeError(
            f"frequency must be str, got {type(frequency).__name__}"
        )
    normalized = frequency.strip().upper()
    if normalized not in SUPPORTED_FREQUENCIES:
        raise ValueError(
            f"frequency must be one of {SUPPORTED_FREQUENCIES}, got {frequency!r}"
        )
    return normalized


def periods_per_year(frequency: str) -> int:
    """Return the number of periods per year for a supported frequency."""
    return PERIODS_PER_YEAR[normalize_frequency(frequency)]


def annual_rate_to_periodic_rate(
    annual_rate: float,
    frequency: str,
) -> float:
    """Convert an annual effective rate to the selected period frequency."""
    rate = _validate_non_bool_real(
        annual_rate,
        "annual_rate",
        min_value=-1.0,
        allow_equal_min=False,
    )
    n = periods_per_year(frequency)
    return (1.0 + rate) ** (1.0 / n) - 1.0


def split_annual_amount(
    annual_amount: float,
    frequency: str,
) -> tuple[float, ...]:
    """Split an annual amount evenly over the selected frequency."""
    amount = _validate_non_bool_real(annual_amount, "annual_amount")
    n = periods_per_year(frequency)
    if n == 1:
        return (amount,)
    return tuple(amount / n for _ in range(n))


@dataclass(frozen=True)
class TimeGridStep:
    """One annual or monthly time-grid step."""

    frequency: str
    step_index: int
    projection_year: int
    reporting_year: int
    period_in_year: int
    event_date: pd.Timestamp

    def __post_init__(self) -> None:
        frequency = normalize_frequency(self.frequency)
        step_index = _validate_non_bool_int(
            self.step_index,
            "step_index",
            min_value=0,
        )
        projection_year = _validate_non_bool_int(
            self.projection_year,
            "projection_year",
            min_value=1,
        )
        reporting_year = _validate_non_bool_int(
            self.reporting_year,
            "reporting_year",
            min_value=0,
        )
        period_in_year = _validate_non_bool_int(
            self.period_in_year,
            "period_in_year",
        )

        if frequency == "ANNUAL" and period_in_year != 1:
            raise ValueError("period_in_year must be 1 for ANNUAL frequency")
        if frequency == "MONTHLY" and not 1 <= period_in_year <= 12:
            raise ValueError(
                "period_in_year must be between 1 and 12 for MONTHLY frequency"
            )

        object.__setattr__(self, "frequency", frequency)
        object.__setattr__(self, "step_index", step_index)
        object.__setattr__(self, "projection_year", projection_year)
        object.__setattr__(self, "reporting_year", reporting_year)
        object.__setattr__(self, "period_in_year", period_in_year)
        object.__setattr__(
            self,
            "event_date",
            _coerce_timestamp(self.event_date, "event_date"),
        )

    def to_dict(self) -> dict[str, object]:
        """Return step fields in stable column order."""
        return {column: getattr(self, column) for column in TIME_GRID_COLUMNS}


def build_time_grid(
    *,
    start_year: int,
    horizon_years: int,
    frequency: str = "ANNUAL",
) -> tuple[TimeGridStep, ...]:
    """Build annual or monthly projection time-grid steps."""
    start = _validate_non_bool_int(start_year, "start_year", min_value=0)
    horizon = _validate_non_bool_int(
        horizon_years,
        "horizon_years",
        min_value=0,
    )
    freq = normalize_frequency(frequency)
    if horizon == 0:
        return ()

    steps: list[TimeGridStep] = []
    step_index = 0
    if freq == "ANNUAL":
        for projection_year in range(1, horizon + 1):
            reporting_year = start + projection_year - 1
            steps.append(
                TimeGridStep(
                    frequency=freq,
                    step_index=step_index,
                    projection_year=projection_year,
                    reporting_year=reporting_year,
                    period_in_year=1,
                    event_date=pd.Timestamp(reporting_year, 12, 31),
                )
            )
            step_index += 1
        return tuple(steps)

    for year_offset in range(horizon):
        reporting_year = start + year_offset
        projection_year = year_offset + 1
        for month in range(1, 13):
            steps.append(
                TimeGridStep(
                    frequency=freq,
                    step_index=step_index,
                    projection_year=projection_year,
                    reporting_year=reporting_year,
                    period_in_year=month,
                    event_date=pd.Timestamp(reporting_year, month, 1)
                    + pd.offsets.MonthEnd(0),
                )
            )
            step_index += 1
    return tuple(steps)


def time_grid_to_dataframe(steps: list | tuple) -> pd.DataFrame:
    """Convert time-grid steps to a DataFrame with canonical columns."""
    if not isinstance(steps, (list, tuple)):
        raise TypeError(f"steps must be list or tuple, got {type(steps).__name__}")
    for i, step in enumerate(steps):
        if not isinstance(step, TimeGridStep):
            raise TypeError(
                f"steps[{i}] must be TimeGridStep, got {type(step).__name__}"
            )
    return pd.DataFrame(
        [step.to_dict() for step in steps],
        columns=list(TIME_GRID_COLUMNS),
    )


def validate_time_grid_dataframe(df: pd.DataFrame) -> bool:
    """Validate a time-grid DataFrame."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"df must be a pandas DataFrame, got {type(df).__name__}")

    missing = [column for column in TIME_GRID_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")
    if list(df.columns) != list(TIME_GRID_COLUMNS):
        raise ValueError(
            f"columns must be in order {list(TIME_GRID_COLUMNS)}, "
            f"got {list(df.columns)}"
        )
    if df.empty:
        return True
    if df[list(TIME_GRID_COLUMNS)].isna().any().any():
        raise ValueError("required columns must not contain missing values")

    previous_event_date: pd.Timestamp | None = None
    for position, (_, row) in enumerate(df.iterrows()):
        step = TimeGridStep(
            frequency=row["frequency"],
            step_index=_coerce_integer_like(row["step_index"], "step_index"),
            projection_year=_coerce_integer_like(
                row["projection_year"],
                "projection_year",
            ),
            reporting_year=_coerce_integer_like(
                row["reporting_year"],
                "reporting_year",
            ),
            period_in_year=_coerce_integer_like(
                row["period_in_year"],
                "period_in_year",
            ),
            event_date=row["event_date"],
        )
        if step.step_index != position:
            raise ValueError(
                "step_index must be strictly increasing from 0 to len(df)-1"
            )
        if previous_event_date is not None and step.event_date < previous_event_date:
            raise ValueError("event_date must be monotonic increasing")
        previous_event_date = step.event_date

    return True
