import math

import pandas as pd
import pytest
from pk_alm.bvg_liability_engine.assumptions import (
    BVGAssumptions,
    FlatRateCurve,
    MortalityAssumptions,
)
from pk_alm.bvg_liability_engine.domain_models.cohorts import ActiveCohort, RetiredCohort
from pk_alm.bvg_liability_engine.orchestration import BVGEngineResult
from pk_alm.bvg_liability_engine.orchestration import run_bvg_engine as _run_bvg_engine
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.bvg_liability_engine.population_dynamics.entry_policies import NoEntryPolicy
from pk_alm.cashflows.schema import CASHFLOW_COLUMNS, validate_cashflow_dataframe

RATE = 0.0176


def run_bvg_engine(
    initial_state,
    horizon_years,
    active_interest_rate,
    retired_interest_rate,
    contribution_multiplier=1.0,
    start_year=2026,
    retirement_age=65,
    capital_withdrawal_fraction=0.35,
    conversion_rate=0.068,
):
    if active_interest_rate <= -1:
        raise ValueError("active_interest_rate must be > -1")
    if retired_interest_rate <= -1:
        raise ValueError("retired_interest_rate must be > -1")
    if isinstance(start_year, bool):
        raise TypeError("start_year must not be bool")
    if start_year < 2000:
        raise ValueError("start_year must be >= 2000")
    if conversion_rate < 0:
        raise ValueError("conversion_rate must be >= 0")
    assumptions = BVGAssumptions(
        start_year=start_year,
        horizon_years=horizon_years,
        retirement_age=retirement_age,
        valuation_terminal_age=max(retirement_age, 1) + 1,
        active_crediting_rate=FlatRateCurve(active_interest_rate),
        retired_interest_rate=FlatRateCurve(retired_interest_rate),
        technical_discount_rate=FlatRateCurve(retired_interest_rate),
        economic_discount_rate=FlatRateCurve(retired_interest_rate),
        salary_growth_rate=FlatRateCurve(0.0),
        conversion_rate=FlatRateCurve(conversion_rate),
        turnover_rate=0.0,
        capital_withdrawal_fraction=capital_withdrawal_fraction,
        contribution_multiplier=contribution_multiplier,
        mortality=MortalityAssumptions(mode="off"),
        entry_policy=NoEntryPolicy(),
    )
    return _run_bvg_engine(initial_state=initial_state, assumptions=assumptions)

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
            assumptions=BVGAssumptions(),
            year_steps=(),
            portfolio_states=(),
            cashflows=pd.DataFrame(columns=list(CASHFLOW_COLUMNS)),
        )


def test_result_validation_wrong_states_type_raises():
    with pytest.raises(TypeError):
        BVGEngineResult(
            assumptions=BVGAssumptions(),
            year_steps=(),
            portfolio_states=[_standard_portfolio()],  # list, not tuple
            cashflows=pd.DataFrame(columns=list(CASHFLOW_COLUMNS)),
        )


def test_result_validation_wrong_cashflows_type_raises():
    with pytest.raises(TypeError):
        BVGEngineResult(
            assumptions=BVGAssumptions(),
            year_steps=(),
            portfolio_states=(_standard_portfolio(),),
            cashflows="not a dataframe",  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# H. Retirement transition is now wired into the engine
# ---------------------------------------------------------------------------


def _act_64_for_engine() -> ActiveCohort:
    return ActiveCohort(
        cohort_id="ACT_64",
        age=64,
        count=2,
        gross_salary_per_person=80000,
        capital_active_per_person=500000,
    )


def test_age_64_one_year_transitions_at_year_end():
    portfolio = BVGPortfolioState(active_cohorts=(_act_64_for_engine(),))
    result = run_bvg_engine(portfolio, 1, RATE, RATE)
    final = result.final_state
    # Cohort has retired; active list is empty
    assert len(final.active_cohorts) == 0
    assert len(final.retired_cohorts) == 1
    rc = final.retired_cohorts[0]
    assert rc.cohort_id == "RET_FROM_ACT_64"
    assert rc.age == 65


def test_age_64_two_years_no_longer_raises():
    portfolio = BVGPortfolioState(active_cohorts=(_act_64_for_engine(),))
    result = run_bvg_engine(portfolio, 2, RATE, RATE)
    # By year 2 the cohort has aged one more year as a retiree
    final = result.final_state
    assert len(final.active_cohorts) == 0
    assert len(final.retired_cohorts) == 1
    assert final.retired_cohorts[0].age == 66


def test_long_horizon_with_only_retirees():
    portfolio = BVGPortfolioState(retired_cohorts=(_ret_70(),))
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


# ---------------------------------------------------------------------------
# J. Engine-level retirement integration tests
# ---------------------------------------------------------------------------


def test_one_year_retirement_pr_and_ka_in_2026():
    portfolio = BVGPortfolioState(active_cohorts=(_act_64_for_engine(),))
    result = run_bvg_engine(portfolio, 1, RATE, RATE)
    df = result.cashflows

    # PR (regular contribution) row first, then KA row
    assert list(df["type"]) == ["PR", "KA"]
    assert (df["time"] == pd.Timestamp("2026-12-31")).all()

    pr_row = df.iloc[0]
    ka_row = df.iloc[1]
    # PR = age credit total at age 64: 2 * 80000_coord(54275) * 0.18 = 19539
    assert pr_row["payoff"] == pytest.approx(19539.0)
    # KA total: -2 * 518569.5 * 0.35
    assert ka_row["payoff"] == pytest.approx(-362998.65)


def test_one_year_retirement_creates_retired_cohort_with_correct_values():
    portfolio = BVGPortfolioState(active_cohorts=(_act_64_for_engine(),))
    result = run_bvg_engine(portfolio, 1, RATE, RATE)

    rc = result.final_state.retired_cohorts[0]
    assert rc.cohort_id == "RET_FROM_ACT_64"
    assert rc.count == 2
    assert rc.annual_pension_per_person == pytest.approx(22920.7719)
    assert rc.capital_rente_per_person == pytest.approx(337070.175)


def test_two_year_retirement_emits_rp_in_year_two():
    portfolio = BVGPortfolioState(active_cohorts=(_act_64_for_engine(),))
    result = run_bvg_engine(portfolio, 2, RATE, RATE)
    df = result.cashflows

    # Year 1 (2026): PR for ACT_64, KA for ACT_64
    # Year 2 (2027): RP for RET_FROM_ACT_64
    times_2026 = df[df["time"] == pd.Timestamp("2026-12-31")]
    times_2027 = df[df["time"] == pd.Timestamp("2027-12-31")]

    assert list(times_2026["type"]) == ["PR", "KA"]
    assert list(times_2027["type"]) == ["RP"]

    # No PR for ACT_64 in 2027
    assert "PR" not in times_2027["type"].tolist()
    # RP comes from the new retired cohort
    assert times_2027.iloc[0]["contractId"] == "RET_FROM_ACT_64"
    # RP = -annual_pension_total = -2 * 22920.7719 = -45841.5438
    assert times_2027.iloc[0]["payoff"] == pytest.approx(-45841.5438)
    assert validate_cashflow_dataframe(df) is True


def test_contribution_multiplier_only_scales_active_pr_with_retirement():
    portfolio = BVGPortfolioState(active_cohorts=(_act_64_for_engine(),))
    result = run_bvg_engine(
        portfolio, 1, RATE, RATE, contribution_multiplier=1.4
    )
    df = result.cashflows
    pr_row = df[df["type"] == "PR"].iloc[0]
    ka_row = df[df["type"] == "KA"].iloc[0]
    assert pr_row["payoff"] == pytest.approx(19539.0 * 1.4)
    # KA is unaffected by contribution_multiplier
    assert ka_row["payoff"] == pytest.approx(-362998.65)


def test_no_ka_when_active_stays_below_retirement_age():
    portfolio = _standard_portfolio()  # ages 40 + 55, neither hits 65 in 2 years
    result = run_bvg_engine(portfolio, 2, RATE, RATE)
    assert "KA" not in set(result.cashflows["type"])
    assert tuple(c.cohort_id for c in result.final_state.active_cohorts) == (
        "ACT_40",
        "ACT_55",
    )


def test_existing_retiree_continues_alongside_new_retirement():
    a64 = _act_64_for_engine()
    existing_retired = RetiredCohort(
        cohort_id="RET_70",
        age=70,
        count=5,
        annual_pension_per_person=30000,
        capital_rente_per_person=450000,
    )
    portfolio = BVGPortfolioState(
        active_cohorts=(a64,),
        retired_cohorts=(existing_retired,),
    )
    result = run_bvg_engine(portfolio, 2, RATE, RATE)
    df = result.cashflows

    # 2026: existing retiree pays RP, ACT_64 pays PR + KA → 3 rows
    rows_2026 = df[df["time"] == pd.Timestamp("2026-12-31")]
    assert sorted(rows_2026["type"].tolist()) == ["KA", "PR", "RP"]
    # The 2026 RP is the existing retiree, not a new one
    rp_2026 = rows_2026[rows_2026["type"] == "RP"].iloc[0]
    assert rp_2026["contractId"] == "RET_70"

    # 2027: existing retiree + newly retired cohort both pay RP → 2 RP rows
    rows_2027 = df[df["time"] == pd.Timestamp("2027-12-31")]
    rp_2027 = rows_2027[rows_2027["type"] == "RP"]
    assert set(rp_2027["contractId"]) == {"RET_70", "RET_FROM_ACT_64"}


# ---------------------------------------------------------------------------
# K. Invalid new engine parameters
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [True, 65.0, "65"])
def test_retirement_age_invalid_type_raises(bad):
    with pytest.raises(TypeError):
        run_bvg_engine(_standard_portfolio(), 1, RATE, RATE, retirement_age=bad)


def test_retirement_age_negative_raises():
    with pytest.raises(ValueError):
        run_bvg_engine(_standard_portfolio(), 1, RATE, RATE, retirement_age=-1)


@pytest.mark.parametrize("bad", [True, "x"])
def test_capital_withdrawal_fraction_invalid_type_raises(bad):
    with pytest.raises(TypeError):
        run_bvg_engine(
            _standard_portfolio(),
            1,
            RATE,
            RATE,
            capital_withdrawal_fraction=bad,
        )


@pytest.mark.parametrize("bad", [-0.01, 1.01])
def test_capital_withdrawal_fraction_invalid_value_raises(bad):
    with pytest.raises(ValueError):
        run_bvg_engine(
            _standard_portfolio(),
            1,
            RATE,
            RATE,
            capital_withdrawal_fraction=bad,
        )


def test_capital_withdrawal_fraction_nan_raises():
    with pytest.raises(ValueError):
        run_bvg_engine(
            _standard_portfolio(),
            1,
            RATE,
            RATE,
            capital_withdrawal_fraction=math.nan,
        )


@pytest.mark.parametrize("bad", [True, "x"])
def test_conversion_rate_invalid_type_raises(bad):
    with pytest.raises(TypeError):
        run_bvg_engine(_standard_portfolio(), 1, RATE, RATE, conversion_rate=bad)


def test_conversion_rate_negative_raises():
    with pytest.raises(ValueError):
        run_bvg_engine(_standard_portfolio(), 1, RATE, RATE, conversion_rate=-0.01)


def test_conversion_rate_nan_raises():
    with pytest.raises(ValueError):
        run_bvg_engine(_standard_portfolio(), 1, RATE, RATE, conversion_rate=math.nan)
