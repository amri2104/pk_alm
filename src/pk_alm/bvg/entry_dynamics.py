"""Stage 2 — Entry Dynamics.

This module specifies how new active members join the pension fund each
projection year. It produces a fresh ``ActiveCohort`` per year and, when
``entry_capital_per_person > 0``, emits an ``IN`` cashflow record for the
incoming Freizügigkeitsleistung.

Implementation status:
    Implemented in Sprint 10 as the Goal-1 Population Dynamics layer.

Year-loop position:
    Entries are applied LAST in the Stage-2 year loop (step 6 in
    ``docs/stage2_spec.md`` section 5), after retirement transitions.
    The entering cohort therefore appears at the end-of-year balance sheet
    and starts contributing from year ``t+1`` onwards.

Scope rules (per ``docs/stage2_spec.md``):
    - Single uniform entry batch per year (entry_age, entry_count,
      entry_salary, entry_capital).
    - ``entry_capital_per_person = 0`` by default → no ``IN`` cashflow
      (zero events would only add noise; ADR 009).
    - Multi-batch / per-age entry distributions are out of Stage-2 scope.
    - ``entry_age >= retirement_age`` is rejected.

Cohort ID scheme:
    ``f"{cohort_id_prefix}_{year}_{nonce}"`` where ``year`` is the calendar
    year and ``nonce`` is a stable string (default ``"0"``). Uniqueness
    against existing cohorts in the portfolio is enforced by
    BVGPortfolioState's existing duplicate-ID check.
"""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass

from pk_alm.bvg.cohorts import ActiveCohort
from pk_alm.bvg.portfolio import BVGPortfolioState
from pk_alm.cashflows.schema import CashflowRecord

DEFAULT_ENTRY_AGE: int = 25
DEFAULT_ENTRY_COUNT_PER_YEAR: int = 1
DEFAULT_ENTRY_GROSS_SALARY: float = 65_000.0
DEFAULT_ENTRY_CAPITAL_PER_PERSON: float = 0.0
DEFAULT_ENTRY_COHORT_ID_PREFIX: str = "ENTRY"

IN_EVENT_TYPE: str = "IN"
"""Stage-2 incoming-Freizügigkeitsleistung cashflow type."""


@dataclass(frozen=True)
class EntryAssumptions:
    """Frozen scenario-level assumption container for new-entrant generation.

    Attributes:
        entry_age: Age of new entrants. Must satisfy
            ``0 <= entry_age < retirement_age`` (retirement_age is enforced
            at engine level, not here, since it is an engine parameter).
        entry_count_per_year: Number of entrants joining each year. Must be
            ``>= 0``. Zero disables entries entirely.
        entry_gross_salary: Annual gross salary at entry. Must be ``>= 0``.
        entry_capital_per_person: Per-person Freizügigkeitsleistung carried
            in. Must be ``>= 0``. Zero (the default, ADR 009) suppresses the
            ``IN`` cashflow entirely.
        cohort_id_prefix: Prefix for generated cohort IDs. Must be a
            non-empty, non-whitespace string. Default ``"ENTRY"``.
    """

    entry_age: int = DEFAULT_ENTRY_AGE
    entry_count_per_year: int = DEFAULT_ENTRY_COUNT_PER_YEAR
    entry_gross_salary: float = DEFAULT_ENTRY_GROSS_SALARY
    entry_capital_per_person: float = DEFAULT_ENTRY_CAPITAL_PER_PERSON
    cohort_id_prefix: str = DEFAULT_ENTRY_COHORT_ID_PREFIX

    def __post_init__(self) -> None:
        if isinstance(self.entry_age, bool):
            raise TypeError("entry_age must not be bool")
        if not isinstance(self.entry_age, int):
            raise TypeError(
                f"entry_age must be int, got {type(self.entry_age).__name__}"
            )
        if self.entry_age < 0:
            raise ValueError(f"entry_age must be >= 0, got {self.entry_age}")

        if isinstance(self.entry_count_per_year, bool):
            raise TypeError("entry_count_per_year must not be bool")
        if not isinstance(self.entry_count_per_year, int):
            raise TypeError(
                "entry_count_per_year must be int, "
                f"got {type(self.entry_count_per_year).__name__}"
            )
        if self.entry_count_per_year < 0:
            raise ValueError(
                "entry_count_per_year must be >= 0, "
                f"got {self.entry_count_per_year}"
            )

        _validate_non_negative_real(
            self.entry_gross_salary, "entry_gross_salary"
        )
        _validate_non_negative_real(
            self.entry_capital_per_person, "entry_capital_per_person"
        )

        if not isinstance(self.cohort_id_prefix, str) or not self.cohort_id_prefix.strip():
            raise ValueError("cohort_id_prefix must be a non-empty string")


def get_default_entry_assumptions() -> EntryAssumptions:
    """Return the Stage-2 baseline default EntryAssumptions instance.

    Defaults (per ``docs/stage2_spec.md`` section 14):
        - entry_age = 25 (first non-zero BVG age-credit bracket)
        - entry_count_per_year = 1 (matches the small demo portfolio)
        - entry_gross_salary = 65_000 CHF (round value, not calibrated)
        - entry_capital_per_person = 0 (ADR 009)
        - cohort_id_prefix = "ENTRY"
    """
    return EntryAssumptions()


def generate_entry_cohort_for_year(
    assumptions: EntryAssumptions,
    calendar_year: int,
    nonce: str = "0",
) -> ActiveCohort | None:
    """Build a fresh ActiveCohort for one projection year.

    Args:
        assumptions: EntryAssumptions for the run.
        calendar_year: Calendar year used inside the cohort_id (e.g. 2026).
        nonce: Suffix to disambiguate multiple entries in the same year.
            Default ``"0"``.

    Returns:
        New ActiveCohort, or ``None`` if
        ``assumptions.entry_count_per_year == 0``.

    Raises:
        TypeError / ValueError on invalid inputs.
    """
    if not isinstance(assumptions, EntryAssumptions):
        raise TypeError(
            f"assumptions must be EntryAssumptions, got {type(assumptions).__name__}"
        )
    if isinstance(calendar_year, bool):
        raise TypeError("calendar_year must not be bool")
    if not isinstance(calendar_year, int):
        raise TypeError(
            f"calendar_year must be int, got {type(calendar_year).__name__}"
        )
    if not isinstance(nonce, str) or not nonce.strip():
        raise ValueError("nonce must be a non-empty string")

    if assumptions.entry_count_per_year == 0:
        return None

    return ActiveCohort(
        cohort_id=f"{assumptions.cohort_id_prefix}_{calendar_year}_{nonce}",
        age=assumptions.entry_age,
        count=assumptions.entry_count_per_year,
        gross_salary_per_person=assumptions.entry_gross_salary,
        capital_active_per_person=assumptions.entry_capital_per_person,
    )


def build_entry_cashflow_record(
    cohort: ActiveCohort,
    event_date: object,
) -> CashflowRecord | None:
    """Build the ``IN`` cashflow record for an entry cohort, if applicable.

    Returns ``None`` when ``cohort.capital_active_per_person == 0`` — no
    zero-payoff entry events are emitted (ADR 009).

    Args:
        cohort: The entry ActiveCohort just generated.
        event_date: Year-end timestamp.

    Returns:
        CashflowRecord of type ``"IN"`` with positive payoff, or ``None``.

    """
    if not isinstance(cohort, ActiveCohort):
        raise TypeError(f"cohort must be ActiveCohort, got {type(cohort).__name__}")
    if cohort.capital_active_per_person == 0:
        return None

    payoff = cohort.count * cohort.capital_active_per_person
    return CashflowRecord(
        contractId=cohort.cohort_id,
        time=event_date,
        type=IN_EVENT_TYPE,
        payoff=payoff,
        nominalValue=payoff,
        currency="CHF",
        source="BVG",
    )


def apply_entries_to_portfolio(
    portfolio: BVGPortfolioState,
    assumptions: EntryAssumptions,
    calendar_year: int,
    event_date: object,
) -> tuple[BVGPortfolioState, tuple[CashflowRecord, ...]]:
    """Add a fresh entry cohort to the portfolio and return any IN records.

    The new cohort is appended to ``portfolio.active_cohorts``. The
    ``projection_year`` of the returned portfolio is identical to the input
    (entries are within-year).

    Args:
        portfolio: BVGPortfolioState to extend.
        assumptions: EntryAssumptions for the run.
        calendar_year: Calendar year used for cohort_id construction.
        event_date: Year-end timestamp for IN records.

    Returns:
        Tuple of:
            - New BVGPortfolioState including the entry cohort (or
              identical to input if entry_count_per_year == 0).
            - Tuple of CashflowRecord IN events. May be empty.

    """
    if not isinstance(portfolio, BVGPortfolioState):
        raise TypeError(
            f"portfolio must be BVGPortfolioState, got {type(portfolio).__name__}"
        )
    if not isinstance(assumptions, EntryAssumptions):
        raise TypeError(
            f"assumptions must be EntryAssumptions, got {type(assumptions).__name__}"
        )

    entry_cohort = generate_entry_cohort_for_year(
        assumptions, calendar_year, nonce="0"
    )
    if entry_cohort is None:
        return portfolio, ()

    in_record = build_entry_cashflow_record(entry_cohort, event_date)
    new_portfolio = BVGPortfolioState(
        projection_year=portfolio.projection_year,
        active_cohorts=tuple(portfolio.active_cohorts) + (entry_cohort,),
        retired_cohorts=portfolio.retired_cohorts,
    )
    in_records = (in_record,) if in_record is not None else ()
    return new_portfolio, in_records


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
