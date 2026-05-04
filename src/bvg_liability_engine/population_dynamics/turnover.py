"""Stage 2 — Turnover.

This module specifies how active members exit a Swiss pension fund mid-career
through Austritt / Freizügigkeitsleistung. It emits ``EX`` cashflow records
for departing vested capital.

Implementation status:
    Implemented in Sprint 10 as the Goal-1 Population Dynamics layer.

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

import math
import numbers
from dataclasses import dataclass

from pk_alm.bvg_liability_engine.domain_models.cohorts import ActiveCohort
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
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
    exited_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.portfolio_state, BVGPortfolioState):
            raise TypeError(
                "portfolio_state must be BVGPortfolioState, "
                f"got {type(self.portfolio_state).__name__}"
            )
        if not isinstance(self.cashflow_records, tuple):
            raise TypeError(
                f"cashflow_records must be tuple, got {type(self.cashflow_records).__name__}"
            )
        for i, record in enumerate(self.cashflow_records):
            if not isinstance(record, CashflowRecord):
                raise TypeError(
                    f"cashflow_records[{i}] must be CashflowRecord, "
                    f"got {type(record).__name__}"
                )
            if record.type != EX_EVENT_TYPE:
                raise ValueError(
                    f"cashflow_records[{i}].type must be {EX_EVENT_TYPE!r}"
                )
            if record.source != "BVG":
                raise ValueError("EX cashflow source must be 'BVG'")
            if record.payoff > 0:
                raise ValueError("EX cashflow payoff must be <= 0")

        residual = _validate_non_bool_real(
            self.rounding_residual_count, "rounding_residual_count"
        )
        if residual < 0:
            raise ValueError(
                "rounding_residual_count must be >= 0, "
                f"got {self.rounding_residual_count}"
            )

        if isinstance(self.exited_count, bool):
            raise TypeError("exited_count must not be bool")
        if not isinstance(self.exited_count, int):
            raise TypeError(
                f"exited_count must be int, got {type(self.exited_count).__name__}"
            )
        if self.exited_count < 0:
            raise ValueError(f"exited_count must be >= 0, got {self.exited_count}")

    @property
    def cashflow_count(self) -> int:
        return len(self.cashflow_records)


def apply_turnover_to_active_cohort(
    cohort: ActiveCohort,
    turnover_rate: float,
    event_date: object,
) -> tuple[ActiveCohort | None, CashflowRecord | None, float, int]:
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
    """
    if not isinstance(cohort, ActiveCohort):
        raise TypeError(f"cohort must be ActiveCohort, got {type(cohort).__name__}")
    rate = _validate_turnover_rate(turnover_rate)

    departing = math.floor(cohort.count * rate)
    residual = cohort.count * rate - departing
    if departing == 0:
        return cohort, None, residual, 0

    vested_capital = departing * cohort.capital_active_per_person
    ex_record = CashflowRecord(
        contractId=cohort.cohort_id,
        time=event_date,
        type=EX_EVENT_TYPE,
        payoff=-vested_capital,
        nominalValue=vested_capital,
        currency="CHF",
        source="BVG",
    )

    remaining = cohort.count - departing
    if remaining == 0:
        surviving = None
    else:
        surviving = ActiveCohort(
            cohort_id=cohort.cohort_id,
            age=cohort.age,
            count=remaining,
            gross_salary_per_person=cohort.gross_salary_per_person,
            capital_active_per_person=cohort.capital_active_per_person,
        )
    return surviving, ex_record, residual, departing


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
    """
    if not isinstance(portfolio, BVGPortfolioState):
        raise TypeError(
            f"portfolio must be BVGPortfolioState, got {type(portfolio).__name__}"
        )
    _validate_turnover_rate(turnover_rate)

    surviving_active: list[ActiveCohort] = []
    records: list[CashflowRecord] = []
    total_residual = 0.0
    exited_count = 0

    for cohort in portfolio.active_cohorts:
        surviving, record, residual, departed = apply_turnover_to_active_cohort(
            cohort, turnover_rate, event_date
        )
        if surviving is not None:
            surviving_active.append(surviving)
        if record is not None:
            records.append(record)
        total_residual += residual
        exited_count += departed

    new_portfolio = BVGPortfolioState(
        projection_year=portfolio.projection_year,
        active_cohorts=tuple(surviving_active),
        retired_cohorts=portfolio.retired_cohorts,
    )
    return TurnoverResult(
        portfolio_state=new_portfolio,
        cashflow_records=tuple(records),
        rounding_residual_count=total_residual,
        exited_count=exited_count,
    )


def _validate_non_bool_real(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be numeric, got {type(value).__name__}")
    fval = float(value)
    if math.isnan(fval):
        raise ValueError(f"{name} must not be NaN")
    return fval


def _validate_turnover_rate(value: object) -> float:
    rate = _validate_non_bool_real(value, "turnover_rate")
    if rate < 0.0 or rate > MAX_PERMITTED_TURNOVER_RATE:
        raise ValueError(
            "turnover_rate must be in "
            f"[0.0, {MAX_PERMITTED_TURNOVER_RATE}], got {rate}"
        )
    return rate
