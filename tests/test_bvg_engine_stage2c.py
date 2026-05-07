import pandas as pd
import pytest

from pk_alm.bvg_liability_engine.assumptions import (
    BVGAssumptions,
    FlatRateCurve,
    MortalityAssumptions,
)
from pk_alm.bvg_liability_engine.assumptions.rate_curves import (
    expand as expand_curve,
    from_dynamic_parameter,
)
from pk_alm.bvg_liability_engine.domain_models.cohorts import ActiveCohort
from pk_alm.bvg_liability_engine.orchestration import BVGEngineResult, run_bvg_engine
from pk_alm.bvg_liability_engine.population_dynamics.entry_dynamics import EntryAssumptions
from pk_alm.bvg_liability_engine.population_dynamics.entry_policies import FixedEntryPolicy
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.cashflows.schema import CASHFLOW_COLUMNS


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


def _default_portfolio() -> BVGPortfolioState:
    return BVGPortfolioState(
        projection_year=0,
        active_cohorts=(
            ActiveCohort("ACT_40", 40, 10, 85_000.0, 120_000.0),
            ActiveCohort("ACT_55", 55, 3, 60_000.0, 300_000.0),
        ),
        retired_cohorts=(),
    )


def run_bvg_engine_stage2c(
    initial,
    *,
    horizon_years,
    active_interest_rate,
    retired_interest_rate,
    salary_growth_rate=0.015,
    turnover_rate=0.02,
    entry_assumptions=None,
    contribution_multiplier=1.4,
    start_year=2026,
    retirement_age=65,
    capital_withdrawal_fraction=0.35,
    conversion_rate=0.068,
) -> BVGEngineResult:
    entry = (
        entry_assumptions
        if entry_assumptions is not None
        else EntryAssumptions()
    )
    assumptions = BVGAssumptions(
        start_year=start_year,
        horizon_years=horizon_years,
        retirement_age=retirement_age,
        valuation_terminal_age=90,
        active_crediting_rate=from_dynamic_parameter(
            active_interest_rate,
            start_year=start_year,
            horizon_years=horizon_years,
        ),
        retired_interest_rate=FlatRateCurve(retired_interest_rate),
        technical_discount_rate=FlatRateCurve(retired_interest_rate),
        economic_discount_rate=FlatRateCurve(retired_interest_rate),
        salary_growth_rate=FlatRateCurve(salary_growth_rate),
        conversion_rate=from_dynamic_parameter(
            conversion_rate,
            start_year=start_year,
            horizon_years=horizon_years,
        ),
        turnover_rate=turnover_rate,
        capital_withdrawal_fraction=capital_withdrawal_fraction,
        contribution_multiplier=contribution_multiplier,
        mortality=MortalityAssumptions(mode="off"),
        entry_policy=FixedEntryPolicy(entry),
    )
    return run_bvg_engine(initial_state=initial, assumptions=assumptions)


def test_all_scalar_inputs_match_stage2a() -> None:
    initial = _default_portfolio()
    stage2a = run_bvg_engine_stage2c(
        initial,
        **PARAMS,
        salary_growth_rate=0.015,
        turnover_rate=0.02,
        entry_assumptions=EntryAssumptions(),
    )
    stage2c = run_bvg_engine_stage2c(
        initial,
        **PARAMS,
        salary_growth_rate=0.015,
        turnover_rate=0.02,
        entry_assumptions=EntryAssumptions(),
    )
    pd.testing.assert_frame_equal(
        stage2c.cashflows.reset_index(drop=True),
        stage2a.cashflows.reset_index(drop=True),
        check_dtype=False,
    )
    assert stage2c.portfolio_states == stage2a.portfolio_states


def test_constant_sequences_match_scalar_inputs() -> None:
    initial = _default_portfolio()
    scalar = run_bvg_engine_stage2c(initial, **PARAMS)
    sequence = run_bvg_engine_stage2c(
        initial,
        **{
            **PARAMS,
            "active_interest_rate": (0.0176,) * PARAMS["horizon_years"],
            "conversion_rate": (0.068,) * PARAMS["horizon_years"],
        },
    )
    pd.testing.assert_frame_equal(sequence.cashflows, scalar.cashflows)
    assert sequence.portfolio_states == scalar.portfolio_states


def test_conversion_rate_reduction_lowers_new_retiree_pension() -> None:
    initial = BVGPortfolioState(
        active_cohorts=(
            ActiveCohort("ACT_64", 64, 1, 0.0, 100_000.0),
            ActiveCohort("ACT_63", 63, 1, 0.0, 100_000.0),
        )
    )
    result = run_bvg_engine_stage2c(
        initial,
        horizon_years=2,
        active_interest_rate=0.0,
        retired_interest_rate=0.0,
        salary_growth_rate=0.0,
        turnover_rate=0.0,
        entry_assumptions=EntryAssumptions(entry_count_per_year=0),
        capital_withdrawal_fraction=0.0,
        conversion_rate=(0.068, 0.060),
    )
    final_retirees = {
        cohort.cohort_id: cohort for cohort in result.final_state.retired_cohorts
    }
    assert final_retirees["RET_FROM_ACT_64"].annual_pension_per_person > (
        final_retirees["RET_FROM_ACT_63"].annual_pension_per_person
    )


def test_lower_active_interest_path_grows_active_capital_more_slowly() -> None:
    initial = BVGPortfolioState(
        active_cohorts=(ActiveCohort("ACT_40", 40, 1, 0.0, 100_000.0),)
    )
    high = run_bvg_engine_stage2c(
        initial,
        horizon_years=2,
        active_interest_rate=(0.02, 0.02),
        retired_interest_rate=0.0,
        salary_growth_rate=0.0,
        turnover_rate=0.0,
        entry_assumptions=EntryAssumptions(entry_count_per_year=0),
    )
    low = run_bvg_engine_stage2c(
        initial,
        horizon_years=2,
        active_interest_rate=(0.02, 0.0),
        retired_interest_rate=0.0,
        salary_growth_rate=0.0,
        turnover_rate=0.0,
        entry_assumptions=EntryAssumptions(entry_count_per_year=0),
    )
    assert low.final_state.total_capital_active < high.final_state.total_capital_active


def test_stage2c_trajectory_fields_have_horizon_length() -> None:
    result = run_bvg_engine_stage2c(
        _default_portfolio(),
        horizon_years=3,
        active_interest_rate=(0.0176, 0.015),
        retired_interest_rate=0.0176,
        conversion_rate=(0.068,),
    )
    assert isinstance(result, BVGEngineResult)
    active_curve = from_dynamic_parameter(
        (0.0176, 0.015), start_year=2026, horizon_years=3
    )
    conversion_curve = from_dynamic_parameter(
        (0.068,), start_year=2026, horizon_years=3
    )
    assert expand_curve(active_curve, start_year=2026, horizon_years=3) == pytest.approx(
        (0.0176, 0.015, 0.015)
    )
    assert expand_curve(
        conversion_curve,
        start_year=2026,
        horizon_years=3,
    ) == pytest.approx((0.068, 0.068, 0.068))


def test_invalid_sequence_length_raises() -> None:
    with pytest.raises(ValueError):
        run_bvg_engine_stage2c(
            _default_portfolio(),
            horizon_years=1,
            active_interest_rate=(0.0176, 0.015),
            retired_interest_rate=0.0176,
        )


def test_zero_horizon_preserves_schema_and_empty_trajectories() -> None:
    result = run_bvg_engine_stage2c(
        _default_portfolio(),
        horizon_years=0,
        active_interest_rate=0.0176,
        retired_interest_rate=0.0176,
    )
    assert result.cashflows.empty
    assert list(result.cashflows.columns) == list(CASHFLOW_COLUMNS)
    assert result.year_steps == ()
