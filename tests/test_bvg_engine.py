import math

import pandas as pd
import pytest
from pk_alm.bvg.cohorts import ActiveCohort, RetiredCohort
from pk_alm.bvg.engine import BVGEngineResult, run_bvg_engine
from pk_alm.bvg.portfolio import BVGPortfolioState
from pk_alm.cashflows.schema import CASHFLOW_COLUMNS, validate_cashflow_dataframe

RATE = 0.0176

# ---------------------------------------------------------------------------
# Standard test portfolio
# ---------------------------------------------------------------------------


def _act_40() -> ActiveCohort:
    return ActiveCohort(
        cohort_id="ACT_40",
        age=40,
        count=10,
        gross_salary_per_person=85000,
        capital_active_per_person=120000,
    )


def _act_55() -> ActiveCohort:
    return ActiveCohort(
        cohort_id="ACT_55",
        age=55,
        count=3,
        gross_salary_per_person=60000,
        capital_active_per_person=300000,
    )


def _ret_70() -> RetiredCohort:
    return RetiredCohort(
        cohort_id="RET_70",
        age=70,
        count=5,
        annual_pension_per_person=30000,
        capital_rente_per_person=450000,
    )


def _standard_portfolio() -> BVGPortfolioState:
    return BVGPortfolioState(
        active_cohorts=(_act_40(), _act_55()),
        retired_cohorts=(_ret_70(),),
    )


# ---------------------------------------------------------------------------
# A. Zero-year horizon
# ---------------------------------------------------------------------------


def test_zero_horizon_returns_initial_state_only():
    initial = _standard_portfolio()
    result = run_bvg_engine(initial, 0, RATE, RATE)

    assert len(result.portfolio_states) == 1
    assert result.initial_state is initial
    assert result.final_state is initial
    assert result.horizon_years == 0
    assert result.cashflow_count == 0
    assert result.cashflows.empty
    assert list(result.cashflows.columns) == list(CASHFLOW_COLUMNS)


# ---------------------------------------------------------------------------
# B. One-year horizon
# ---------------------------------------------------------------------------


def test_one_year_states_count():
    result = run_bvg_engine(_standard_portfolio(), 1, RATE, RATE)
    assert len(result.portfolio_states) == 2
    assert result.horizon_years == 1


def test_one_year_cashflow_shape():
    result = run_bvg_engine(_standard_portfolio(), 1, RATE, RATE)
    assert result.cashflows.shape == (3, 7)
    assert list(result.cashflows.columns) == list(CASHFLOW_COLUMNS)


def test_one_year_cashflow_validates():
    result = run_bvg_engine(_standard_portfolio(), 1, RATE, RATE)
    assert validate_cashflow_dataframe(result.cashflows) is True


def test_one_year_cashflow_dates():
    result = run_bvg_engine(_standard_portfolio(), 1, RATE, RATE)
    expected = pd.Timestamp("2026-12-31")
    assert (result.cashflows["time"] == expected).all()


def test_one_year_cashflow_contract_ids():
    result = run_bvg_engine(_standard_portfolio(), 1, RATE, RATE)
    assert list(result.cashflows["contractId"]) == ["ACT_40", "ACT_55", "RET_70"]


def test_one_year_payoffs():
    result = run_bvg_engine(_standard_portfolio(), 1, RATE, RATE)
    payoffs = list(result.cashflows["payoff"])
    assert payoffs[0] == pytest.approx(59275.0)
    assert payoffs[1] == pytest.approx(18508.5)
    assert payoffs[2] == pytest.approx(-150_000.0)


def test_one_year_final_state_active_cohorts():
    result = run_bvg_engine(_standard_portfolio(), 1, RATE, RATE)
    final = result.final_state
    a0, a1 = final.active_cohorts
    assert a0.age == 41
    assert a0.capital_active_per_person == pytest.approx(128039.5)
    assert a1.age == 56
    assert a1.capital_active_per_person == pytest.approx(311449.5)


def test_one_year_final_state_retired_cohort():
    result = run_bvg_engine(_standard_portfolio(), 1, RATE, RATE)
    r0 = result.final_state.retired_cohorts[0]
    assert r0.age == 71
    assert r0.capital_rente_per_person == pytest.approx(427392.0)


# ---------------------------------------------------------------------------
# C. Two-year horizon
# ---------------------------------------------------------------------------


def test_two_year_states_count():
    result = run_bvg_engine(_standard_portfolio(), 2, RATE, RATE)
    assert len(result.portfolio_states) == 3


def test_two_year_cashflow_shape():
    result = run_bvg_engine(_standard_portfolio(), 2, RATE, RATE)
    assert result.cashflows.shape == (6, 7)


def test_two_year_cashflow_dates():
    result = run_bvg_engine(_standard_portfolio(), 2, RATE, RATE)
    times = list(result.cashflows["time"])
    expected = (
        [pd.Timestamp("2026-12-31")] * 3 + [pd.Timestamp("2027-12-31")] * 3
    )
    assert times == expected


def test_two_year_final_state():
    result = run_bvg_engine(_standard_portfolio(), 2, RATE, RATE)
    a0, a1 = result.final_state.active_cohorts
    r0 = result.final_state.retired_cohorts[0]
    assert a0.age == 42
    assert a0.capital_active_per_person == pytest.approx(136220.4952)
    assert a1.age == 57
    assert a1.capital_active_per_person == pytest.approx(323100.5112)
    assert r0.age == 72
    assert r0.capital_rente_per_person == pytest.approx(404386.0992)


# ---------------------------------------------------------------------------
# D. Contribution multiplier pass-through
# ---------------------------------------------------------------------------


def test_contribution_multiplier_scales_active_only():
    result = run_bvg_engine(
        _standard_portfolio(), 1, RATE, RATE, contribution_multiplier=1.4
    )
    payoffs = list(result.cashflows["payoff"])
    assert payoffs[0] == pytest.approx(59275.0 * 1.4)
    assert payoffs[1] == pytest.approx(18508.5 * 1.4)
    # pension payment is not scaled
    assert payoffs[2] == pytest.approx(-150_000.0)


# ---------------------------------------------------------------------------
# E. Different interest rates
# ---------------------------------------------------------------------------


def test_different_rates_not_swapped():
    result = run_bvg_engine(
        _standard_portfolio(),
        horizon_years=1,
        active_interest_rate=0.02,
        retired_interest_rate=0.01,
    )
    a0 = result.final_state.active_cohorts[0]
    r0 = result.final_state.retired_cohorts[0]

    # ACT_40 used 0.02: 120000 * 1.02 + 5927.5 = 128327.5
    assert a0.capital_active_per_person == pytest.approx(128327.5)
    # RET_70 used 0.01: (450000 - 30000) * 1.01 = 424200.0
    assert r0.capital_rente_per_person == pytest.approx(424200.0)

    # And the active value should NOT match what 0.01 would produce
    active_if_swapped = 120000 * 1.01 + 5927.5
    assert a0.capital_active_per_person != pytest.approx(active_if_swapped)


# ---------------------------------------------------------------------------
# F. Immutability
# ---------------------------------------------------------------------------


def test_engine_does_not_mutate_initial_state():
    initial = _standard_portfolio()
    snap_year = initial.projection_year
    snap_active_ages = tuple(c.age for c in initial.active_cohorts)
    snap_active_capital = tuple(
        c.capital_active_per_person for c in initial.active_cohorts
    )
    snap_retired_ages = tuple(c.age for c in initial.retired_cohorts)
    snap_retired_capital = tuple(
        c.capital_rente_per_person for c in initial.retired_cohorts
    )

    result = run_bvg_engine(initial, 2, RATE, RATE)

    assert initial.projection_year == snap_year
    assert tuple(c.age for c in initial.active_cohorts) == snap_active_ages
    assert (
        tuple(c.capital_active_per_person for c in initial.active_cohorts)
        == snap_active_capital
    )
    assert tuple(c.age for c in initial.retired_cohorts) == snap_retired_ages
    assert (
        tuple(c.capital_rente_per_person for c in initial.retired_cohorts)
        == snap_retired_capital
    )
    assert result.final_state is not initial


# ---------------------------------------------------------------------------
# G. BVGEngineResult properties and frozen behavior
# ---------------------------------------------------------------------------


def test_result_properties():
    initial = _standard_portfolio()
    result = run_bvg_engine(initial, 2, RATE, RATE)
    assert result.initial_state is initial
    assert result.final_state is result.portfolio_states[-1]
    assert result.horizon_years == 2
    assert result.cashflow_count == 6


def test_result_is_frozen():
    result = run_bvg_engine(_standard_portfolio(), 1, RATE, RATE)
    with pytest.raises(Exception):
        result.portfolio_states = ()  # type: ignore[misc]


def test_result_validation_empty_states_raises():
    with pytest.raises(ValueError):
        BVGEngineResult(
            portfolio_states=(),
            cashflows=pd.DataFrame(columns=list(CASHFLOW_COLUMNS)),
        )


def test_result_validation_wrong_states_type_raises():
    with pytest.raises(TypeError):
        BVGEngineResult(
            portfolio_states=[_standard_portfolio()],  # list, not tuple
            cashflows=pd.DataFrame(columns=list(CASHFLOW_COLUMNS)),
        )


def test_result_validation_wrong_cashflows_type_raises():
    with pytest.raises(TypeError):
        BVGEngineResult(
            portfolio_states=(_standard_portfolio(),),
            cashflows="not a dataframe",  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# H. Retirement guard
# ---------------------------------------------------------------------------


def test_retirement_guard_age_64_one_year_allowed():
    a64 = ActiveCohort(
        cohort_id="ACT_64",
        age=64,
        count=2,
        gross_salary_per_person=80000,
        capital_active_per_person=500000,
    )
    portfolio = BVGPortfolioState(active_cohorts=(a64,))
    result = run_bvg_engine(portfolio, 1, RATE, RATE)
    assert result.final_state.active_cohorts[0].age == 65


def test_retirement_guard_age_64_two_years_raises():
    a64 = ActiveCohort(
        cohort_id="ACT_64",
        age=64,
        count=2,
        gross_salary_per_person=80000,
        capital_active_per_person=500000,
    )
    portfolio = BVGPortfolioState(active_cohorts=(a64,))
    with pytest.raises(ValueError, match="beyond age 65"):
        run_bvg_engine(portfolio, 2, RATE, RATE)


def test_retirement_guard_empty_active_cohorts_no_raise():
    portfolio = BVGPortfolioState(retired_cohorts=(_ret_70(),))
    # Long horizon should still work because there are no active cohorts.
    result = run_bvg_engine(portfolio, 10, RATE, RATE)
    assert result.horizon_years == 10


# ---------------------------------------------------------------------------
# I. Invalid inputs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [None, "not a portfolio", 42])
def test_invalid_initial_state_type_raises(bad):
    with pytest.raises(TypeError):
        run_bvg_engine(bad, 1, RATE, RATE)


def test_horizon_bool_raises():
    with pytest.raises(TypeError):
        run_bvg_engine(_standard_portfolio(), True, RATE, RATE)


def test_horizon_not_int_raises():
    with pytest.raises(TypeError):
        run_bvg_engine(_standard_portfolio(), 1.5, RATE, RATE)


def test_horizon_negative_raises():
    with pytest.raises(ValueError):
        run_bvg_engine(_standard_portfolio(), -1, RATE, RATE)


@pytest.mark.parametrize("bad", [True, "x"])
def test_active_rate_invalid_type_raises(bad):
    with pytest.raises(TypeError):
        run_bvg_engine(_standard_portfolio(), 1, bad, RATE)


def test_active_rate_at_minus_one_raises():
    with pytest.raises(ValueError):
        run_bvg_engine(_standard_portfolio(), 1, -1.0, RATE)


def test_active_rate_nan_raises():
    with pytest.raises(ValueError):
        run_bvg_engine(_standard_portfolio(), 1, math.nan, RATE)


@pytest.mark.parametrize("bad", [True, "x"])
def test_retired_rate_invalid_type_raises(bad):
    with pytest.raises(TypeError):
        run_bvg_engine(_standard_portfolio(), 1, RATE, bad)


def test_retired_rate_at_minus_one_raises():
    with pytest.raises(ValueError):
        run_bvg_engine(_standard_portfolio(), 1, RATE, -1.0)


def test_retired_rate_nan_raises():
    with pytest.raises(ValueError):
        run_bvg_engine(_standard_portfolio(), 1, RATE, math.nan)


@pytest.mark.parametrize("bad", [True, "x"])
def test_contribution_multiplier_invalid_type_raises(bad):
    with pytest.raises(TypeError):
        run_bvg_engine(
            _standard_portfolio(), 1, RATE, RATE, contribution_multiplier=bad
        )


def test_contribution_multiplier_negative_raises():
    with pytest.raises(ValueError):
        run_bvg_engine(
            _standard_portfolio(), 1, RATE, RATE, contribution_multiplier=-0.5
        )


def test_contribution_multiplier_nan_raises():
    with pytest.raises(ValueError):
        run_bvg_engine(
            _standard_portfolio(), 1, RATE, RATE, contribution_multiplier=math.nan
        )


@pytest.mark.parametrize("bad", [True, "2026"])
def test_start_year_invalid_type_raises(bad):
    with pytest.raises(TypeError):
        run_bvg_engine(_standard_portfolio(), 1, RATE, RATE, start_year=bad)


def test_start_year_too_low_raises():
    with pytest.raises(ValueError):
        run_bvg_engine(_standard_portfolio(), 1, RATE, RATE, start_year=1999)
