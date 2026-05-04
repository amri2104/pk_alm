"""Stage 2 — Salary Dynamics.

This module specifies how active-cohort gross salaries evolve year over year.
Stage 2 uses a single deterministic scenario-level scalar
``salary_growth_rate``.

Implementation status:
    Implemented in Sprint 10 as the Goal-1 Population Dynamics layer.

Year-loop position:
    Salary growth is applied AFTER one-year projection (which advances age and
    credits interest) and BEFORE retirement transitions. See
    ``docs/stage2_spec.md`` section 5 for the canonical loop ordering and
    ADR 008 in ``docs/decisions.md`` for the rationale.

Scope rules (per ``docs/stage2_spec.md``):
    - Single uniform scalar ``salary_growth_rate``.
    - ``g >= 0`` enforced; deflation is rejected in Stage 2.
    - Applies only to ``ActiveCohort.gross_salary_per_person``. Coordinated
      salary, age credits, and PR contributions are recomputed by the existing
      Stage-1 BVG formulas; no formula changes.
    - Per-age or per-cohort growth curves and stochastic salary growth are
      out of Stage-2 scope (see ADR 007).
"""

from __future__ import annotations

import math
import numbers

from pk_alm.bvg_liability_engine.domain_models.cohorts import ActiveCohort
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState

DEFAULT_SALARY_GROWTH_RATE: float = 0.015
"""Stage-2 baseline default: 1.5 % per year (long-run Swiss nominal wage growth)."""

MAX_PERMITTED_SALARY_GROWTH_RATE: float = 0.10
"""Hard upper bound to catch obviously wrong inputs (10 % p.a.). Configurable later."""


def apply_salary_growth_to_active_cohort(
    cohort: ActiveCohort,
    salary_growth_rate: float,
) -> ActiveCohort:
    """Return a new ActiveCohort with ``gross_salary_per_person`` scaled.

    Formula::

        gross_salary_next = gross_salary_current * (1 + salary_growth_rate)

    All other ActiveCohort fields (``cohort_id``, ``age``, ``count``,
    ``capital_active_per_person``) are passed through unchanged. The returned
    cohort is a fresh dataclass instance; the input is not mutated.

    Args:
        cohort: ActiveCohort whose salary should be grown.
        salary_growth_rate: Non-negative growth rate per year. Default in
            scenarios is ``DEFAULT_SALARY_GROWTH_RATE``.

    Returns:
        New ActiveCohort with updated gross salary.

    Raises:
        TypeError: If ``cohort`` is not an ActiveCohort, or
            ``salary_growth_rate`` is bool / non-numeric.
        ValueError: If ``salary_growth_rate < 0``, ``> MAX_PERMITTED_SALARY_GROWTH_RATE``,
            or NaN.
    """
    if not isinstance(cohort, ActiveCohort):
        raise TypeError(f"cohort must be ActiveCohort, got {type(cohort).__name__}")
    rate = _validate_salary_growth_rate(salary_growth_rate)
    return ActiveCohort(
        cohort_id=cohort.cohort_id,
        age=cohort.age,
        count=cohort.count,
        gross_salary_per_person=cohort.gross_salary_per_person * (1.0 + rate),
        capital_active_per_person=cohort.capital_active_per_person,
    )


def apply_salary_growth_to_portfolio(
    portfolio: BVGPortfolioState,
    salary_growth_rate: float,
) -> BVGPortfolioState:
    """Return a new BVGPortfolioState with all active cohorts' salaries grown.

    Calls :func:`apply_salary_growth_to_active_cohort` for each active cohort.
    Retired cohorts pass through untouched (pension amounts in Stage 2 are
    fixed at retirement; pension indexation is out of scope).

    The ``projection_year`` field of the returned state is **identical** to
    the input. Salary growth is a within-year transformation; it does not
    advance projection time. The Stage-1 ``project_portfolio_one_year``
    function is the single owner of projection-time advancement.

    Args:
        portfolio: BVGPortfolioState whose active cohorts should be grown.
        salary_growth_rate: Non-negative growth rate per year.

    Returns:
        New BVGPortfolioState with updated active cohorts and unchanged
        retired cohorts.

    Raises:
        TypeError: If ``portfolio`` is not a BVGPortfolioState.
        ValueError: If ``salary_growth_rate`` violates the bounds in
            :func:`apply_salary_growth_to_active_cohort`.
    """
    if not isinstance(portfolio, BVGPortfolioState):
        raise TypeError(
            f"portfolio must be BVGPortfolioState, got {type(portfolio).__name__}"
        )
    return BVGPortfolioState(
        projection_year=portfolio.projection_year,
        active_cohorts=tuple(
            apply_salary_growth_to_active_cohort(c, salary_growth_rate)
            for c in portfolio.active_cohorts
        ),
        retired_cohorts=portfolio.retired_cohorts,
    )


def _validate_salary_growth_rate(value: object) -> float:
    if isinstance(value, bool):
        raise TypeError("salary_growth_rate must not be bool")
    if not isinstance(value, numbers.Real):
        raise TypeError(
            f"salary_growth_rate must be numeric, got {type(value).__name__}"
        )
    rate = float(value)
    if math.isnan(rate):
        raise ValueError("salary_growth_rate must not be NaN")
    if rate < 0.0 or rate > MAX_PERMITTED_SALARY_GROWTH_RATE:
        raise ValueError(
            "salary_growth_rate must be in "
            f"[0.0, {MAX_PERMITTED_SALARY_GROWTH_RATE}], got {rate}"
        )
    return rate
