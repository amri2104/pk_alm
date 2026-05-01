"""Stage 2 — BVG Engine v2 (BAUPLAN, not yet implemented).

This is the Stage-2 counterpart to ``src/pk_alm/bvg/engine.py``. It runs the
full Stage-2 year loop: PR/RP → turnover → projection → salary growth →
retirement → entries.

Implementation status:
    All public functions raise ``NotImplementedError("Stage 2 Bauplan:
    implementation deferred")`` until Sprint 10.

Architectural rule (ADR 010):
    The Stage-1 engine ``run_bvg_engine`` and its file ``engine.py`` MUST
    NOT be modified by Stage 2. This module is parallel.

Equivalence guarantee (mandatory test):
    ``run_bvg_engine_stage2`` with::

        salary_growth_rate = 0.0
        turnover_rate      = 0.0
        entry_assumptions  = EntryAssumptions(entry_count_per_year=0)

    must produce **bit-identical** ``portfolio_states`` and ``cashflows`` to
    ``run_bvg_engine`` for the same other inputs. This pins the regression
    contract between Stage 1 and Stage 2.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from pk_alm.bvg.entry_dynamics import EntryAssumptions
from pk_alm.bvg.portfolio import BVGPortfolioState


@dataclass(frozen=True)
class Stage2EngineResult:
    """Frozen container for one Stage-2 BVG engine run.

    Mirrors ``BVGEngineResult`` (Stage 1) and adds Stage-2-specific
    bookkeeping for transparency.

    Attributes:
        portfolio_states: Tuple of BVGPortfolioState snapshots, length
            ``horizon_years + 1``. ``portfolio_states[0]`` equals the input
            ``initial_state``.
        cashflows: Validated CashflowRecord DataFrame in the canonical
            seven-column schema. Includes PR / RP / KA from Stage 1
            mechanics plus EX / IN from Stage 2 mechanics. ``source`` is
            always ``"BVG"``.
        turnover_rounding_residual_count: Tuple of length ``horizon_years``
            with the per-year fractional-count residual from turnover
            (see ``turnover.py`` for the formula). Reported, not reapplied.
        per_year_entries: Tuple of length ``horizon_years`` with the count
            of new active members joining each year.
        per_year_exits: Tuple of length ``horizon_years`` with the count
            of active members departing each year (turnover, not retirement).
        per_year_retirements: Tuple of length ``horizon_years`` with the
            count of active members retiring each year (existing Stage-1
            mechanic, exposed here for the Stage-2 demographic summary).
        salary_growth_rate: Echo of the input parameter for traceability.
        turnover_rate: Echo of the input parameter for traceability.
        entry_assumptions: Echo of the input EntryAssumptions for
            traceability.
    """

    portfolio_states: tuple[BVGPortfolioState, ...]
    cashflows: pd.DataFrame
    turnover_rounding_residual_count: tuple[float, ...]
    per_year_entries: tuple[int, ...]
    per_year_exits: tuple[int, ...]
    per_year_retirements: tuple[int, ...]
    salary_growth_rate: float
    turnover_rate: float
    entry_assumptions: EntryAssumptions

    def __post_init__(self) -> None:
        # Validation rules (final, enforced in Sprint 10):
        # - portfolio_states: tuple of BVGPortfolioState, len >= 1
        # - cashflows: validate_cashflow_dataframe (all source == "BVG")
        # - turnover_rounding_residual_count: tuple of float
        # - per_year_entries / per_year_exits / per_year_retirements:
        #     tuple of int >= 0, all length == horizon_years
        # - salary_growth_rate: float >= 0
        # - turnover_rate: float in [0, MAX_PERMITTED_TURNOVER_RATE]
        # - entry_assumptions: EntryAssumptions
        raise NotImplementedError(
            "Stage 2 Bauplan: Stage2EngineResult validation deferred (Sprint 10)"
        )

    @property
    def initial_state(self) -> BVGPortfolioState:
        return self.portfolio_states[0]

    @property
    def final_state(self) -> BVGPortfolioState:
        return self.portfolio_states[-1]

    @property
    def horizon_years(self) -> int:
        return len(self.portfolio_states) - 1

    @property
    def cashflow_count(self) -> int:
        return len(self.cashflows)

    @property
    def total_entries(self) -> int:
        return sum(self.per_year_entries)

    @property
    def total_exits(self) -> int:
        return sum(self.per_year_exits)

    @property
    def total_retirements(self) -> int:
        return sum(self.per_year_retirements)


def run_bvg_engine_stage2(
    initial_state: BVGPortfolioState,
    horizon_years: int,
    active_interest_rate: float,
    retired_interest_rate: float,
    salary_growth_rate: float = 0.015,
    turnover_rate: float = 0.02,
    entry_assumptions: EntryAssumptions | None = None,
    contribution_multiplier: float = 1.4,
    start_year: int = 2026,
    retirement_age: int = 65,
    capital_withdrawal_fraction: float = 0.35,
    conversion_rate: float = 0.068,
) -> Stage2EngineResult:
    """Project a BVG portfolio for ``horizon_years`` with Stage-2 dynamics.

    Per-year canonical loop (see ``docs/stage2_spec.md`` section 5):

      1. PR/RP cashflows from current state at year-start
      2. Turnover (active counts reduced; EX cashflows emitted)
      3. Project portfolio one year (interest credit + age + 1)
      4. Salary growth (gross_salary scaled on remaining active cohorts)
      5. Retirement transitions (KA cashflows for retiring active cohorts)
      6. New entrants (fresh active cohort appended; optional IN cashflow)

    All six steps reuse Stage-1 building blocks where applicable. Only
    steps 2, 4, 6 are Stage-2-specific.

    Args:
        initial_state: Starting BVGPortfolioState (year 0).
        horizon_years: Number of projection years. Non-negative.
        active_interest_rate: Annual rate credited to active capital.
        retired_interest_rate: Annual rate credited to retiree capital.
        salary_growth_rate: Annual scalar applied to gross salaries
            (Stage-2 specific). Default 1.5 %.
        turnover_rate: Annual fraction of active members who leave through
            Austritt (Stage-2 specific). Default 2.0 %.
        entry_assumptions: EntryAssumptions for new-entrant generation
            (Stage-2 specific). If ``None``, the Stage-2 default is used:
            ``get_default_entry_assumptions()`` from ``entry_dynamics.py``.
        contribution_multiplier: Same Stage-1 semantics; default 1.4.
        start_year: Calendar year of the first projection step. Default 2026.
        retirement_age: Same Stage-1 semantics; default 65.
        capital_withdrawal_fraction: Same Stage-1 semantics; default 0.35.
        conversion_rate: Same Stage-1 semantics; default 0.068.

    Returns:
        Stage2EngineResult with the projected states, validated cashflow
        DataFrame, and Stage-2 demographic counters.

    Raises:
        TypeError / ValueError on invalid inputs.
        NotImplementedError: Always, until Sprint 10.

    Stage-1 equivalence:
        With ``salary_growth_rate=0``, ``turnover_rate=0``, and
        ``entry_assumptions=EntryAssumptions(entry_count_per_year=0)``, this
        function MUST return portfolio states and cashflows that are
        bit-identical to ``run_bvg_engine`` for the same other inputs.
        This is enforced as a mandatory regression test.
    """
    raise NotImplementedError(
        "Stage 2 Bauplan: run_bvg_engine_stage2 implementation deferred (Sprint 10)"
    )
