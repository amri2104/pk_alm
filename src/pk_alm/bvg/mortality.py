"""Educational EK 0105 mortality helpers for the Stage-2B prototype.

EK 0105 is used here only as a simplified teaching table. It is not presented
as a current Swiss pension-fund standard. For real pension-fund valuation,
BVG 2020 / VZ 2020 style tables would be more appropriate; those are outside
the scope of this prototype.
"""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass
from importlib import resources

import pandas as pd

MORTALITY_MODE_OFF = "off"
MORTALITY_MODE_EK0105 = "ek0105"

EKM_0105 = "EKM 0105"
EKF_0105 = "EKF 0105"
DEFAULT_EK0105_TABLE_ID = EKF_0105
SUPPORTED_EK0105_TABLE_IDS = (EKM_0105, EKF_0105)

MORTALITY_SOURCE_CAVEAT = (
    "EK 0105 is a simplified educational mortality input. BVG 2020 / VZ 2020 "
    "would be more appropriate for real Swiss pension-fund valuation, but are "
    "out of scope for this prototype."
)

_TABLE_FILES = {
    EKM_0105: "ekm_0105.csv",
    EKF_0105: "ekf_0105.csv",
}


@dataclass(frozen=True)
class MortalityTable:
    """Validated one-year death probabilities by integer age."""

    table_id: str
    rows: tuple[tuple[int, float, float], ...]
    source_caveat: str = MORTALITY_SOURCE_CAVEAT

    def __post_init__(self) -> None:
        if self.table_id not in SUPPORTED_EK0105_TABLE_IDS:
            raise ValueError(
                f"table_id must be one of {SUPPORTED_EK0105_TABLE_IDS}, "
                f"got {self.table_id!r}"
            )
        if not isinstance(self.rows, tuple) or not self.rows:
            raise TypeError("rows must be a non-empty tuple")

        previous_age: int | None = None
        for i, row in enumerate(self.rows):
            if not isinstance(row, tuple) or len(row) != 3:
                raise TypeError(f"rows[{i}] must be a 3-tuple")
            age, qx, lx = row
            if isinstance(age, bool) or not isinstance(age, int):
                raise TypeError(f"rows[{i}].age must be int")
            q = _validate_probability(qx, f"rows[{i}].qx")
            l = _validate_non_negative_real(lx, f"rows[{i}].lx")
            if previous_age is not None and age != previous_age + 1:
                raise ValueError("mortality table ages must be contiguous")
            previous_age = age
            if q != qx or l != lx:
                object.__setattr__(
                    self,
                    "rows",
                    tuple((int(a), float(qv), float(lv)) for a, qv, lv in self.rows),
                )
                break

    @property
    def min_age(self) -> int:
        return self.rows[0][0]

    @property
    def max_age(self) -> int:
        return self.rows[-1][0]

    def qx(self, age: int) -> float:
        age = _validate_age(age)
        if age < self.min_age or age > self.max_age:
            raise ValueError(
                f"age must be in [{self.min_age}, {self.max_age}], got {age}"
            )
        return self.rows[age - self.min_age][1]

    def px(self, age: int) -> float:
        return 1.0 - self.qx(age)

    def lx(self, age: int) -> float:
        age = _validate_age(age)
        if age < self.min_age or age > self.max_age:
            raise ValueError(
                f"age must be in [{self.min_age}, {self.max_age}], got {age}"
            )
        return self.rows[age - self.min_age][2]

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows, columns=["age", "qx", "lx"])


def load_ek0105_table(table_id: str = DEFAULT_EK0105_TABLE_ID) -> MortalityTable:
    """Load one bundled EK 0105 table."""
    if table_id not in SUPPORTED_EK0105_TABLE_IDS:
        raise ValueError(
            f"table_id must be one of {SUPPORTED_EK0105_TABLE_IDS}, got {table_id!r}"
        )
    package = "pk_alm.bvg.data"
    with resources.files(package).joinpath(_TABLE_FILES[table_id]).open(
        "r", encoding="utf-8"
    ) as f:
        df = pd.read_csv(f)

    if list(df.columns) != ["age", "qx", "lx"]:
        raise ValueError("mortality table CSV must have columns age,qx,lx")
    rows = tuple(
        (int(row.age), float(row.qx), float(row.lx))
        for row in df.itertuples(index=False)
    )
    return MortalityTable(table_id=table_id, rows=rows)


def survival_factor(table: MortalityTable, start_age: int, years: int) -> float:
    """Return survival from `start_age` to `start_age + years`."""
    if not isinstance(table, MortalityTable):
        raise TypeError(f"table must be MortalityTable, got {type(table).__name__}")
    start = _validate_age(start_age)
    years = _validate_years(years)
    factor = 1.0
    for offset in range(years):
        age = start + offset
        if age > table.max_age:
            return 0.0
        factor *= table.px(age)
    return factor


def survival_factors(
    table: MortalityTable,
    start_age: int,
    horizon_years: int,
) -> tuple[float, ...]:
    """Return survival factors for offsets 0..horizon_years."""
    horizon = _validate_years(horizon_years)
    return tuple(survival_factor(table, start_age, t) for t in range(horizon + 1))


def expected_pension_payment(
    *,
    count: int,
    annual_pension_per_person: float,
    survival_probability: float,
) -> float:
    """Return expected RP cashflow with fund-perspective negative sign."""
    if isinstance(count, bool) or not isinstance(count, int):
        raise TypeError("count must be int")
    if count < 0:
        raise ValueError("count must be >= 0")
    pension = _validate_non_negative_real(
        annual_pension_per_person, "annual_pension_per_person"
    )
    survival = _validate_probability(survival_probability, "survival_probability")
    return -(count * pension * survival)


def _validate_age(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"age must be int, got {type(value).__name__}")
    if value < 0:
        raise ValueError(f"age must be >= 0, got {value}")
    return value


def _validate_years(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"years must be int, got {type(value).__name__}")
    if value < 0:
        raise ValueError(f"years must be >= 0, got {value}")
    return value


def _validate_non_negative_real(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be numeric, got {type(value).__name__}")
    fval = float(value)
    if math.isnan(fval):
        raise ValueError(f"{name} must not be NaN")
    if fval < 0:
        raise ValueError(f"{name} must be >= 0, got {fval}")
    return fval


def _validate_probability(value: object, name: str) -> float:
    fval = _validate_non_negative_real(value, name)
    if fval > 1:
        raise ValueError(f"{name} must be <= 1, got {fval}")
    return fval
