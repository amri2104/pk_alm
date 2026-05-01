"""Stage 2 — Salary Dynamics (BAUPLAN, not yet implemented).

This module specifies how active-cohort gross salaries evolve year over year.
Stage 2 uses a single deterministic scenario-level scalar
``salary_growth_rate``.

Implementation status:
    All public functions in this module raise
    ``NotImplementedError("Stage 2 Bauplan: implementation deferred")``.
    The signatures, validation rules, docstrings, and module-level constants
    are final. Sprint 10 (Stage-2 implementation sprint) will fill the
    function bodies without changing the signatures.

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

from pk_alm.bvg.cohorts import ActiveCohort
from pk_alm.bvg.portfolio import BVGPortfolioState

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
        NotImplementedError: Always, until Sprint 10.
    """
    raise NotImplementedError(
        "Stage 2 Bauplan: apply_salary_growth_to_active_cohort "
        "implementation deferred (Sprint 10)"
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
        NotImplementedError: Always, until Sprint 10.
    """
    raise NotImplementedError(
        "Stage 2 Bauplan: apply_salary_growth_to_portfolio "
        "implementation deferred (Sprint 10)"
    )
