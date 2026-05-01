import pandas as pd
import pytest

from pk_alm.bvg.engine import run_bvg_engine
from pk_alm.bvg.engine_stage2 import Stage2EngineResult, run_bvg_engine_stage2
from pk_alm.bvg.entry_dynamics import EntryAssumptions
from pk_alm.cashflows.schema import CASHFLOW_COLUMNS
from pk_alm.scenarios.stage1_baseline import build_default_stage1_portfolio


PARAMS = dict(
    horizon_years=12,
    active_interest_rate=0.0176,
    retired_interest_rate=0.0176,
    contribution_multiplier=1.4,
    start_year=2026,
    retirement_age=65,
    capital_withdrawal_fraction=0.35,
    conversion_rate=0.068,
)


def test_stage2_with_zero_levers_equals_stage1() -> None:
    initial = build_default_stage1_portfolio()
    stage1 = run_bvg_engine(initial, **PARAMS)
    stage2 = run_bvg_engine_stage2(
        initial,
        **PARAMS,
        salary_growth_rate=0.0,
        turnover_rate=0.0,
        entry_assumptions=EntryAssumptions(entry_count_per_year=0),
    )
    pd.testing.assert_frame_equal(
        stage1.cashflows.reset_index(drop=True),
        stage2.cashflows.reset_index(drop=True),
        check_dtype=False,
    )
    assert stage2.portfolio_states == stage1.portfolio_states
    assert stage2.per_year_entries == (0,) * PARAMS["horizon_years"]
    assert stage2.per_year_exits == (0,) * PARAMS["horizon_years"]


def test_zero_horizon_preserves_schema_and_counter_lengths() -> None:
    result = run_bvg_engine_stage2(
        build_default_stage1_portfolio(),
        horizon_years=0,
        active_interest_rate=0.0176,
        retired_interest_rate=0.0176,
    )
    assert isinstance(result, Stage2EngineResult)
    assert result.cashflows.empty
    assert list(result.cashflows.columns) == list(CASHFLOW_COLUMNS)
    assert result.turnover_rounding_residual_count == ()
    assert result.per_year_entries == ()
    assert result.per_year_exits == ()
    assert result.per_year_retirements == ()


def test_salary_growth_increases_later_contribution_base() -> None:
    initial = build_default_stage1_portfolio()
    flat = run_bvg_engine_stage2(
        initial,
        horizon_years=2,
        active_interest_rate=0.0176,
        retired_interest_rate=0.0176,
        salary_growth_rate=0.0,
        turnover_rate=0.0,
        entry_assumptions=EntryAssumptions(entry_count_per_year=0),
        contribution_multiplier=1.4,
    )
    grown = run_bvg_engine_stage2(
        initial,
        horizon_years=2,
        active_interest_rate=0.0176,
        retired_interest_rate=0.0176,
        salary_growth_rate=0.05,
        turnover_rate=0.0,
        entry_assumptions=EntryAssumptions(entry_count_per_year=0),
        contribution_multiplier=1.4,
    )
    flat_2027_pr = flat.cashflows.loc[
        (flat.cashflows["time"] == pd.Timestamp("2027-12-31"))
        & (flat.cashflows["type"] == "PR"),
        "payoff",
    ].sum()
    grown_2027_pr = grown.cashflows.loc[
        (grown.cashflows["time"] == pd.Timestamp("2027-12-31"))
        & (grown.cashflows["type"] == "PR"),
        "payoff",
    ].sum()
    assert grown_2027_pr > flat_2027_pr


def test_turnover_produces_ex_cashflows_and_decreases_active_count() -> None:
    initial = build_default_stage1_portfolio()
    result = run_bvg_engine_stage2(
        initial,
        horizon_years=1,
        active_interest_rate=0.0176,
        retired_interest_rate=0.0176,
        salary_growth_rate=0.0,
        turnover_rate=0.2,
        entry_assumptions=EntryAssumptions(entry_count_per_year=0),
    )
    ex_rows = result.cashflows[result.cashflows["type"] == "EX"]
    assert not ex_rows.empty
    assert (ex_rows["payoff"] < 0).all()
    assert sum(result.per_year_exits) == 2
    assert result.final_state.active_count_total < initial.active_count_total


def test_entries_append_entry_cohorts_and_contribute_next_year() -> None:
    result = run_bvg_engine_stage2(
        build_default_stage1_portfolio(),
        horizon_years=2,
        active_interest_rate=0.0176,
        retired_interest_rate=0.0176,
        salary_growth_rate=0.0,
        turnover_rate=0.0,
        entry_assumptions=EntryAssumptions(entry_count_per_year=2),
    )
    assert result.per_year_entries == (2, 2)
    assert "ENTRY_2026_0" in result.portfolio_states[1].cohort_ids
    first_year_entry_pr = result.cashflows.loc[
        (result.cashflows["time"] == pd.Timestamp("2026-12-31"))
        & (result.cashflows["contractId"] == "ENTRY_2026_0")
        & (result.cashflows["type"] == "PR")
    ]
    second_year_entry_pr = result.cashflows.loc[
        (result.cashflows["time"] == pd.Timestamp("2027-12-31"))
        & (result.cashflows["contractId"] == "ENTRY_2026_0")
        & (result.cashflows["type"] == "PR")
    ]
    assert first_year_entry_pr.empty
    assert not second_year_entry_pr.empty


def test_retirement_counter_counts_persons_before_transition() -> None:
    initial = build_default_stage1_portfolio()
    result = run_bvg_engine_stage2(
        initial,
        horizon_years=10,
        active_interest_rate=0.0176,
        retired_interest_rate=0.0176,
        salary_growth_rate=0.0,
        turnover_rate=0.0,
        entry_assumptions=EntryAssumptions(entry_count_per_year=0),
    )
    assert result.per_year_retirements[8] == 0
    assert result.per_year_retirements[9] == 3
    assert result.total_retirements == 3


@pytest.mark.parametrize("entry_age", [65, 70])
def test_entry_age_at_or_above_retirement_age_rejected(entry_age: int) -> None:
    with pytest.raises(ValueError):
        run_bvg_engine_stage2(
            build_default_stage1_portfolio(),
            horizon_years=1,
            active_interest_rate=0.0176,
            retired_interest_rate=0.0176,
            entry_assumptions=EntryAssumptions(entry_age=entry_age),
        )
