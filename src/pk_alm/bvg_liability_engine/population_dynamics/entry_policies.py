"""Entry policies for the BVG liability engine.

Three deterministic policies decide how many new active cohorts join at the
end of each projection year:

- :class:`NoEntryPolicy` — closed fund. No entries.
- :class:`FixedEntryPolicy` — wraps :class:`EntryAssumptions`; emits a fixed
  number of entrants each year.
- :class:`ReplacementEntryPolicy` — entrants replace a fraction of the
  exits and retirements from the same year, using
  ``round(replacement_ratio * (exited + retired))``.
"""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from pk_alm.bvg_liability_engine.domain_models.cohorts import ActiveCohort
from pk_alm.bvg_liability_engine.population_dynamics.entry_dynamics import (
    EntryAssumptions,
    generate_entry_cohort_for_year,
)


@runtime_checkable
class EntryPolicy(Protocol):
    """Protocol for entry policies.

    Implementations return zero or more :class:`ActiveCohort` instances to
    add to the portfolio at year end. ``year`` is the calendar year of the
    closing snapshot. ``exited_count`` and ``retired_count`` are the counts
    that left the active population in the same year.
    """

    def entries_for_year(
        self,
        year: int,
        exited_count: int,
        retired_count: int,
    ) -> tuple[ActiveCohort, ...]:
        ...


def _validate_int(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, int):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")
    return value


def _validate_count(value: object, name: str) -> int:
    n = _validate_int(value, name)
    if n < 0:
        raise ValueError(f"{name} must be >= 0, got {n}")
    return n


def _validate_unit_interval(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be numeric, got {type(value).__name__}")
    fval = float(value)
    if math.isnan(fval):
        raise ValueError(f"{name} must not be NaN")
    if fval < 0.0:
        raise ValueError(f"{name} must be >= 0, got {fval}")
    return fval


@dataclass(frozen=True)
class NoEntryPolicy:
    """Closed-fund entry policy: never produces entries."""

    def entries_for_year(
        self,
        year: int,
        exited_count: int,
        retired_count: int,
    ) -> tuple[ActiveCohort, ...]:
        _validate_int(year, "year")
        _validate_count(exited_count, "exited_count")
        _validate_count(retired_count, "retired_count")
        return ()


@dataclass(frozen=True)
class FixedEntryPolicy:
    """Fixed-cohort entry policy.

    Each year emits exactly one entry cohort, parameterized by
    :class:`EntryAssumptions`. ``entry_count_per_year == 0`` produces no
    entries.
    """

    assumptions: EntryAssumptions

    def __post_init__(self) -> None:
        if not isinstance(self.assumptions, EntryAssumptions):
            raise TypeError(
                "assumptions must be EntryAssumptions, got "
                f"{type(self.assumptions).__name__}"
            )

    def entries_for_year(
        self,
        year: int,
        exited_count: int,
        retired_count: int,
    ) -> tuple[ActiveCohort, ...]:
        _validate_int(year, "year")
        _validate_count(exited_count, "exited_count")
        _validate_count(retired_count, "retired_count")
        cohort = generate_entry_cohort_for_year(self.assumptions, year)
        if cohort is None:
            return ()
        return (cohort,)


@dataclass(frozen=True)
class ReplacementEntryPolicy:
    """Replacement entry policy.

    Entrants per year ``= round(replacement_ratio * (exited + retired))``.
    Each entrant is realized as one fresh :class:`ActiveCohort` with the
    template's age, salary, and per-person capital — but ``count = 1`` and a
    unique ``cohort_id``.
    """

    template: EntryAssumptions
    replacement_ratio: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.template, EntryAssumptions):
            raise TypeError(
                "template must be EntryAssumptions, got "
                f"{type(self.template).__name__}"
            )
        object.__setattr__(
            self,
            "replacement_ratio",
            _validate_unit_interval(self.replacement_ratio, "replacement_ratio"),
        )

    def entries_for_year(
        self,
        year: int,
        exited_count: int,
        retired_count: int,
    ) -> tuple[ActiveCohort, ...]:
        _validate_int(year, "year")
        ex = _validate_count(exited_count, "exited_count")
        rt = _validate_count(retired_count, "retired_count")
        n = int(round(self.replacement_ratio * (ex + rt)))
        if n <= 0:
            return ()
        cohorts: list[ActiveCohort] = []
        for i in range(n):
            cohorts.append(
                ActiveCohort(
                    cohort_id=(
                        f"{self.template.cohort_id_prefix}_{year}_R{i}"
                    ),
                    age=self.template.entry_age,
                    count=1,
                    gross_salary_per_person=self.template.entry_gross_salary,
                    capital_active_per_person=self.template.entry_capital_per_person,
                )
            )
        return tuple(cohorts)
