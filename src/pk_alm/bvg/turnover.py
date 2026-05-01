"""Stage 2 — Turnover (BAUPLAN, not yet implemented).

This module specifies how active members exit a Swiss pension fund mid-career
through Austritt / Freizügigkeitsleistung. It emits ``EX`` cashflow records
for departing vested capital.

Implementation status:
    All public functions in this module raise
    ``NotImplementedError("Stage 2 Bauplan: implementation deferred")``.
    The signatures, validation rules, docstrings, and module-level constants
    are final. Sprint 10 will fill the function bodies.

Year-loop position:
    Turnover is applied AFTER PR/RP cashflow emission for the current state
    and BEFORE one-year projection. See ``docs/stage2_spec.md`` section 5
    for the canonical loop ordering and ADR 008 in ``docs/decisions.md`` for
    the rationale (leavers earn their last year's PR but do not collect
    that year's interest credit).

Sign convention:
    ``EX`` cashflow ``payoff`` is **negative** (outflow from the fund),
    consistent with ``KA`` and ``RP``.

Scope rules (per ``docs/stage2_spec.md``):
    - Full vesting from year 1 (BVG-conservative simplification).
    - Single deterministic scalar ``turnover_rate`` applied to all active
      cohorts uniformly.
    - Counts use ``floor(count * turnover_rate)``; the rounding residual is
      reported separately for transparency.
    - Cohorts with ``count == 0`` after turnover are removed from the
      portfolio.
    - Retirees are not subject to turnover (mortality is Stage 3).
"""

from __future__ import annotations

from dataclasses import dataclass

from pk_alm.bvg.cohorts import ActiveCohort
from pk_alm.bvg.portfolio import BVGPortfolioState
from pk_alm.cashflows.schema import CashflowRecord

DEFAULT_TURNOVER_RATE: float = 0.02
"""Stage-2 baseline default: 2 % per year, net of retirements."""

MAX_PERMITTED_TURNOVER_RATE: float = 0.50
"""Hard upper bound to reject pathological scenarios. Configurable later."""

EX_EVENT_TYPE: str = "EX"
"""Stage-2 exit-cashflow type. Stage 1 uses PR / RP / KA only."""


@dataclass(frozen=True)
class TurnoverResult:
    """Frozen container holding the post-turnover portfolio and EX cashflows.

    Attributes:
        portfolio_state: New BVGPortfolioState with reduced active counts.
            Retired cohorts pass through unchanged. Projection year is
            identical to the input (turnover is within-year).
        cashflow_records: Tuple of EX records, one per cohort that had at
            least one departing member. Cohorts with ``floor(count * rate)
            == 0`` produce no EX record.
        rounding_residual_count: ``sum( count * rate - floor(count * rate) )``
            across all active cohorts, in count units. Reported in the
            Stage-2 demographic summary for transparency. Not reapplied.
    """

    portfolio_state: BVGPortfolioState
    cashflow_records: tuple[CashflowRecord, ...]
    rounding_residual_count: float

    def __post_init__(self) -> None:
        # Validation rules (final, will be enforced in Sprint 10):
        # - portfolio_state: BVGPortfolioState
        # - cashflow_records: tuple of CashflowRecord; all type == "EX";
        #   all source == "BVG"; all payoff <= 0.
        # - rounding_residual_count: float in [0.0, len(active_cohorts)).
        raise NotImplementedError(
            "Stage 2 Bauplan: TurnoverResult validation deferred (Sprint 10)"
        )

    @property
    def cashflow_count(self) -> int:
        return len(self.cashflow_records)


def apply_turnover_to_active_cohort(
    cohort: ActiveCohort,
    turnover_rate: float,
    event_date: object,
) -> tuple[ActiveCohort | None, CashflowRecord | None, float]:
    """Apply turnover to one active cohort.

    Formula::

        departing = floor( count * turnover_rate )
        remaining = count - departing
        residual  = count * turnover_rate - departing
        EX_payoff = -( departing * capital_active_per_person )

    Args:
        cohort: ActiveCohort to apply turnover to.
        turnover_rate: Non-negative scalar in
            ``[0, MAX_PERMITTED_TURNOVER_RATE]``.
        event_date: Year-end timestamp for the EX record (passed to
            ``CashflowRecord.time``).

    Returns:
        Tuple of:
            - New ActiveCohort with reduced count, or ``None`` if all
              members departed (``remaining == 0``).
            - CashflowRecord of type ``"EX"``, or ``None`` if no member
              departed (``departing == 0``).
            - Float rounding residual ``count * rate - floor(count * rate)``
              in ``[0.0, 1.0)``.

    Raises:
        TypeError: Argument-type errors.
        ValueError: Out-of-range rates, invalid event_date.
        NotImplementedError: Always, until Sprint 10.
    """
    raise NotImplementedError(
        "Stage 2 Bauplan: apply_turnover_to_active_cohort "
        "implementation deferred (Sprint 10)"
    )


def apply_turnover_to_portfolio(
    portfolio: BVGPortfolioState,
    turnover_rate: float,
    event_date: object,
) -> TurnoverResult:
    """Apply turnover to all active cohorts in a portfolio.

    Iterates over ``portfolio.active_cohorts``, applies turnover to each via
    :func:`apply_turnover_to_active_cohort`, and assembles a TurnoverResult.
    Retired cohorts pass through unchanged.

    The returned ``portfolio_state.projection_year`` is identical to
    ``portfolio.projection_year`` — turnover does not advance projection time.

    Args:
        portfolio: Input BVGPortfolioState.
        turnover_rate: Non-negative scalar in
            ``[0, MAX_PERMITTED_TURNOVER_RATE]``.
        event_date: Year-end timestamp for EX records.

    Returns:
        TurnoverResult with the new portfolio state, EX records, and
        rounding residual.

    Raises:
        TypeError: Argument-type errors.
        ValueError: Out-of-range turnover_rate.
        NotImplementedError: Always, until Sprint 10.
    """
    raise NotImplementedError(
        "Stage 2 Bauplan: apply_turnover_to_portfolio "
        "implementation deferred (Sprint 10)"
    )
