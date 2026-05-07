"""Generic BVG liability engine.

Single entry point :func:`run_bvg_engine` driven by a frozen
:class:`BVGAssumptions` container. Replaces the per-stage legacy variants in
:mod:`.legacy`. All variant behaviour (open vs. closed fund, mortality on/off,
flat vs. time-varying rates, monthly cashflows) is encoded as assumption
configuration, not a different engine.
"""

from __future__ import annotations

import pandas as pd

from pk_alm.bvg_liability_engine.assumptions.bvg_assumptions import BVGAssumptions
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.bvg_liability_engine.orchestration.result import BVGEngineResult
from pk_alm.bvg_liability_engine.orchestration.year_step import BVGYearStep
from pk_alm.bvg_liability_engine.pension_logic.cashflow_generation import (
    generate_bvg_cashflow_dataframe_for_state,
)
from pk_alm.bvg_liability_engine.pension_logic.projection import project_portfolio_one_year
from pk_alm.bvg_liability_engine.pension_logic.retirement_transition import (
    apply_retirement_transitions_to_portfolio,
)
from pk_alm.bvg_liability_engine.population_dynamics.entry_dynamics import (
    build_entry_cashflow_record,
)
from pk_alm.bvg_liability_engine.population_dynamics.salary_dynamics import (
    apply_salary_growth_to_portfolio,
)
from pk_alm.bvg_liability_engine.population_dynamics.turnover import (
    apply_turnover_to_portfolio,
)
from pk_alm.cashflows.schema import (
    CASHFLOW_COLUMNS,
    CashflowRecord,
    cashflow_records_to_dataframe,
    validate_cashflow_dataframe,
)


def _empty_cashflow_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=list(CASHFLOW_COLUMNS))


def _apply_entry_policy(
    state: BVGPortfolioState,
    assumptions: BVGAssumptions,
    year: int,
    exited_count: int,
    retired_count: int,
    event_date: pd.Timestamp,
) -> tuple[BVGPortfolioState, pd.DataFrame, int]:
    cohorts = assumptions.entry_policy.entries_for_year(
        year, exited_count, retired_count
    )
    if not cohorts:
        return state, _empty_cashflow_frame(), 0

    in_records: list[CashflowRecord] = []
    for cohort in cohorts:
        record = build_entry_cashflow_record(cohort, event_date)
        if record is not None:
            in_records.append(record)
    in_df = cashflow_records_to_dataframe(in_records) if in_records else _empty_cashflow_frame()

    new_state = BVGPortfolioState(
        projection_year=state.projection_year,
        active_cohorts=tuple(state.active_cohorts) + tuple(cohorts),
        retired_cohorts=state.retired_cohorts,
    )
    entry_count = sum(c.count for c in cohorts)
    return new_state, in_df, entry_count


def _split_monthly(
    df: pd.DataFrame, *, periods: int = 12
) -> pd.DataFrame:
    """Split each annual cashflow row into ``periods`` equal sub-period rows.

    Used in monthly mode. ``payoff`` is divided evenly across ``periods``.
    The ``time`` of period ``p`` (0-indexed) is the last day of month ``p+1``
    of the row's calendar year. ``nominalValue`` is preserved on every row
    (it is a balance-sheet quantity, not a flow).
    """
    if df.empty:
        return df.copy()
    out_rows: list[dict[str, object]] = []
    for _, row in df.iterrows():
        annual_payoff = float(row["payoff"])
        per_period = annual_payoff / periods
        ts = pd.Timestamp(row["time"])
        year = ts.year
        for p in range(periods):
            month = p + 1
            month_end = pd.Timestamp(f"{year}-{month:02d}-01") + pd.offsets.MonthEnd(0)
            out_rows.append(
                {
                    "contractId": row["contractId"],
                    "time": month_end,
                    "type": row["type"],
                    "payoff": per_period,
                    "nominalValue": row["nominalValue"],
                    "currency": row["currency"],
                    "source": row["source"],
                }
            )
    return pd.DataFrame(out_rows, columns=list(CASHFLOW_COLUMNS))


def run_bvg_engine(
    *,
    initial_state: BVGPortfolioState,
    assumptions: BVGAssumptions,
) -> BVGEngineResult:
    """Project a BVG portfolio for the configured horizon.

    Year-loop ordering (per ADR 008 / docs/stage2_spec.md §5):

    1. Regular PR/RP cashflows from the current state (event date Dec 31).
    2. Turnover (``EX`` cashflows; active counts reduced).
    3. Project the portfolio one year forward (interest credit + age + 1).
    4. Salary growth on remaining active cohorts.
    5. Retirement transitions (``KA`` cashflows; active → retired).
    6. New entrants from :class:`EntryPolicy` (``IN`` cashflows where applicable).

    Stage 1 is reproduced by setting ``turnover_rate=0``, salary growth to
    zero, and ``entry_policy=NoEntryPolicy``.

    Monthly cashflow frequency emits 12 sub-period rows per annual flow with
    per-period payoff = annual / 12. State transitions remain annual.
    """
    if not isinstance(initial_state, BVGPortfolioState):
        raise TypeError(
            f"initial_state must be BVGPortfolioState, got {type(initial_state).__name__}"
        )
    if not isinstance(assumptions, BVGAssumptions):
        raise TypeError(
            f"assumptions must be BVGAssumptions, got {type(assumptions).__name__}"
        )

    horizon = assumptions.horizon_years
    start_year = assumptions.start_year

    states: list[BVGPortfolioState] = [initial_state]
    year_steps: list[BVGYearStep] = []
    annual_cashflow_frames: list[pd.DataFrame] = []
    current = initial_state

    for step in range(horizon):
        year = start_year + step
        event_date = pd.Timestamp(f"{year}-12-31")

        opening = current

        # 1. Regular PR/RP from current state.
        regular_df = generate_bvg_cashflow_dataframe_for_state(
            current, event_date, assumptions.contribution_multiplier
        )
        post_regular_state = current

        # 2. Turnover -> EX records.
        turnover_result = apply_turnover_to_portfolio(
            current, assumptions.turnover_rate, event_date
        )
        if turnover_result.cashflow_records:
            ex_df = cashflow_records_to_dataframe(turnover_result.cashflow_records)
        else:
            ex_df = _empty_cashflow_frame()
        post_turnover_state = turnover_result.portfolio_state
        exited_count = turnover_result.exited_count

        # 3. Project one year forward (interest credit + age + 1).
        active_rate = float(assumptions.active_crediting_rate.value_at(year))
        retired_rate = float(assumptions.retired_interest_rate.value_at(year))
        projected = project_portfolio_one_year(
            post_turnover_state, active_rate, retired_rate
        )
        post_projection_state = projected

        # 4. Salary growth on remaining actives.
        salary_g = float(assumptions.salary_growth_rate.value_at(year))
        grown = apply_salary_growth_to_portfolio(projected, salary_g)
        post_salary_growth_state = grown

        # 5. Retirement transitions -> KA records.
        retired_count = sum(
            cohort.count
            for cohort in grown.active_cohorts
            if cohort.age >= assumptions.retirement_age
        )
        conv_rate = float(assumptions.conversion_rate.value_at(year))
        transition = apply_retirement_transitions_to_portfolio(
            grown,
            event_date,
            retirement_age=assumptions.retirement_age,
            capital_withdrawal_fraction=assumptions.capital_withdrawal_fraction,
            conversion_rate=conv_rate,
        )
        if transition.cashflow_records:
            retire_df = cashflow_records_to_dataframe(transition.cashflow_records)
        else:
            retire_df = _empty_cashflow_frame()
        post_retirement_state = transition.portfolio_state

        # 6. New entrants per entry policy -> IN records.
        post_entry_state, in_df, entry_count = _apply_entry_policy(
            post_retirement_state,
            assumptions,
            year,
            exited_count,
            retired_count,
            event_date,
        )

        annual_year_df = pd.concat(
            [regular_df, ex_df, retire_df, in_df], ignore_index=True
        )
        validate_cashflow_dataframe(annual_year_df)

        if assumptions.cashflow_frequency == "monthly":
            # Only PR and RP split into 12 monthly rows. KA / EX / IN are
            # event-driven retirement / exit / entry flows; they stay on the
            # year-end timestamp.
            regular_df_out = _split_monthly(regular_df, periods=12)
            ex_df_out = ex_df
            retire_df_out = retire_df
            in_df_out = in_df
            year_df = pd.concat(
                [regular_df_out, ex_df_out, retire_df_out, in_df_out],
                ignore_index=True,
            )
            validate_cashflow_dataframe(year_df)
        else:
            year_df = annual_year_df
            regular_df_out = regular_df
            ex_df_out = ex_df
            retire_df_out = retire_df
            in_df_out = in_df

        year_steps.append(
            BVGYearStep(
                year=year,
                opening_state=opening,
                post_regular_cashflow_state=post_regular_state,
                post_turnover_state=post_turnover_state,
                post_projection_state=post_projection_state,
                post_salary_growth_state=post_salary_growth_state,
                post_retirement_state=post_retirement_state,
                closing_state=post_entry_state,
                regular_cashflows=regular_df_out,
                turnover_cashflows=ex_df_out,
                retirement_cashflows=retire_df_out,
                entry_cashflows=in_df_out,
                year_cashflows=year_df,
                exited_count=exited_count,
                retired_count=retired_count,
                entry_count=entry_count,
            )
        )

        annual_cashflow_frames.append(year_df)
        current = post_entry_state
        states.append(current)

    if annual_cashflow_frames:
        cashflows = pd.concat(annual_cashflow_frames, ignore_index=True)
    else:
        cashflows = _empty_cashflow_frame()
    validate_cashflow_dataframe(cashflows)

    return BVGEngineResult(
        assumptions=assumptions,
        year_steps=tuple(year_steps),
        portfolio_states=tuple(states),
        cashflows=cashflows,
    )
