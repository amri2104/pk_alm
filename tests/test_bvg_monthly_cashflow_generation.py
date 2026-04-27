import math

import pandas as pd
import pytest

from pk_alm.bvg.cashflow_generation import (
    generate_bvg_cashflow_dataframe_for_state,
)
from pk_alm.bvg.cohorts import ActiveCohort, RetiredCohort
from pk_alm.bvg.monthly_cashflow_generation import (
    MONTHS_PER_YEAR,
    generate_monthly_bvg_cashflow_dataframe_for_state,
    generate_monthly_bvg_cashflow_records_for_state,
)
from pk_alm.bvg.portfolio import BVGPortfolioState
from pk_alm.cashflows.schema import CASHFLOW_COLUMNS, validate_cashflow_dataframe

REPORTING_YEAR = 2026


# ---------------------------------------------------------------------------
# Shared cohorts
# ---------------------------------------------------------------------------

ACT_40 = ActiveCohort(
    cohort_id="ACT_40",
    age=40,
    count=10,
    gross_salary_per_person=85000,
    capital_active_per_person=120000,
)
ACT_55 = ActiveCohort(
    cohort_id="ACT_55",
    age=55,
    count=3,
    gross_salary_per_person=60000,
    capital_active_per_person=300000,
)
RET_70 = RetiredCohort(
    cohort_id="RET_70",
    age=70,
    count=5,
    annual_pension_per_person=30000,
    capital_rente_per_person=450000,
)
PORTFOLIO = BVGPortfolioState(
    active_cohorts=(ACT_40, ACT_55),
    retired_cohorts=(RET_70,),
)


# ---------------------------------------------------------------------------
# A. Standard monthly records
# ---------------------------------------------------------------------------


def test_standard_records_count_is_36():
    records = generate_monthly_bvg_cashflow_records_for_state(
        PORTFOLIO, REPORTING_YEAR, contribution_multiplier=1.4
    )
    assert isinstance(records, tuple)
    assert len(records) == MONTHS_PER_YEAR * 3


def test_standard_records_first_month_order():
    records = generate_monthly_bvg_cashflow_records_for_state(
        PORTFOLIO, REPORTING_YEAR, contribution_multiplier=1.4
    )
    first_three = records[:3]
    assert tuple(r.contractId for r in first_three) == (
        "ACT_40",
        "ACT_55",
        "RET_70",
    )
    assert tuple(r.type for r in first_three) == ("PR", "PR", "RP")


def test_standard_records_first_event_date_is_january_month_end():
    records = generate_monthly_bvg_cashflow_records_for_state(
        PORTFOLIO, REPORTING_YEAR
    )
    assert records[0].time == pd.Timestamp("2026-01-31")


def test_standard_records_last_event_date_is_december_month_end():
    records = generate_monthly_bvg_cashflow_records_for_state(
        PORTFOLIO, REPORTING_YEAR
    )
    assert records[-1].time == pd.Timestamp("2026-12-31")


def test_pr_payoffs_positive():
    records = generate_monthly_bvg_cashflow_records_for_state(
        PORTFOLIO, REPORTING_YEAR, contribution_multiplier=1.4
    )
    pr_payoffs = [r.payoff for r in records if r.type == "PR"]
    assert pr_payoffs
    assert all(p > 0 for p in pr_payoffs)


def test_rp_payoffs_negative():
    records = generate_monthly_bvg_cashflow_records_for_state(
        PORTFOLIO, REPORTING_YEAR
    )
    rp_payoffs = [r.payoff for r in records if r.type == "RP"]
    assert rp_payoffs
    assert all(p < 0 for p in rp_payoffs)


# ---------------------------------------------------------------------------
# B. Monthly amount checks
# ---------------------------------------------------------------------------


def test_monthly_amounts_match_expected_cohort_values():
    records = generate_monthly_bvg_cashflow_records_for_state(
        PORTFOLIO, REPORTING_YEAR, contribution_multiplier=1.4
    )
    by_cohort: dict[str, list[float]] = {"ACT_40": [], "ACT_55": [], "RET_70": []}
    for record in records:
        by_cohort[record.contractId].append(record.payoff)

    assert len(by_cohort["ACT_40"]) == MONTHS_PER_YEAR
    assert len(by_cohort["ACT_55"]) == MONTHS_PER_YEAR
    assert len(by_cohort["RET_70"]) == MONTHS_PER_YEAR

    for payoff in by_cohort["ACT_40"]:
        assert payoff == pytest.approx(59275.0 * 1.4 / 12)
    for payoff in by_cohort["ACT_55"]:
        assert payoff == pytest.approx(18508.5 * 1.4 / 12)
    for payoff in by_cohort["RET_70"]:
        assert payoff == pytest.approx(-150_000.0 / 12)


def test_monthly_nominal_values_match_capital_totals():
    records = generate_monthly_bvg_cashflow_records_for_state(
        PORTFOLIO, REPORTING_YEAR
    )
    nominal_by_cohort = {record.contractId: record.nominalValue for record in records}
    assert nominal_by_cohort["ACT_40"] == pytest.approx(1_200_000.0)
    assert nominal_by_cohort["ACT_55"] == pytest.approx(900_000.0)
    assert nominal_by_cohort["RET_70"] == pytest.approx(2_250_000.0)


# ---------------------------------------------------------------------------
# C. Monthly totals equal annual totals
# ---------------------------------------------------------------------------


def test_monthly_pr_total_equals_annual_pr_total():
    annual_df = generate_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, f"{REPORTING_YEAR}-12-31", contribution_multiplier=1.4
    )
    monthly_df = generate_monthly_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, REPORTING_YEAR, contribution_multiplier=1.4
    )
    annual_pr = annual_df.loc[annual_df["type"] == "PR", "payoff"].sum()
    monthly_pr = monthly_df.loc[monthly_df["type"] == "PR", "payoff"].sum()
    assert monthly_pr == pytest.approx(annual_pr)


def test_monthly_rp_total_equals_annual_rp_total():
    annual_df = generate_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, f"{REPORTING_YEAR}-12-31"
    )
    monthly_df = generate_monthly_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, REPORTING_YEAR
    )
    annual_rp = annual_df.loc[annual_df["type"] == "RP", "payoff"].sum()
    monthly_rp = monthly_df.loc[monthly_df["type"] == "RP", "payoff"].sum()
    assert monthly_rp == pytest.approx(annual_rp)


# ---------------------------------------------------------------------------
# D. DataFrame helper
# ---------------------------------------------------------------------------


def test_dataframe_has_canonical_columns():
    df = generate_monthly_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, REPORTING_YEAR
    )
    assert list(df.columns) == list(CASHFLOW_COLUMNS)


def test_dataframe_validates():
    df = generate_monthly_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, REPORTING_YEAR
    )
    assert validate_cashflow_dataframe(df) is True


def test_dataframe_shape_is_36_by_7():
    df = generate_monthly_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, REPORTING_YEAR
    )
    assert df.shape == (36, len(CASHFLOW_COLUMNS))


# ---------------------------------------------------------------------------
# E. Empty portfolio
# ---------------------------------------------------------------------------


def test_empty_portfolio_returns_empty_tuple():
    records = generate_monthly_bvg_cashflow_records_for_state(
        BVGPortfolioState(), REPORTING_YEAR
    )
    assert records == ()


def test_empty_portfolio_returns_empty_valid_dataframe():
    df = generate_monthly_bvg_cashflow_dataframe_for_state(
        BVGPortfolioState(), REPORTING_YEAR
    )
    assert df.empty
    assert list(df.columns) == list(CASHFLOW_COLUMNS)
    assert validate_cashflow_dataframe(df) is True


# ---------------------------------------------------------------------------
# F. Contribution multiplier
# ---------------------------------------------------------------------------


def test_default_multiplier_does_not_scale_pr():
    default_records = generate_monthly_bvg_cashflow_records_for_state(
        PORTFOLIO, REPORTING_YEAR
    )
    explicit_records = generate_monthly_bvg_cashflow_records_for_state(
        PORTFOLIO, REPORTING_YEAR, contribution_multiplier=1.0
    )
    for default, explicit in zip(default_records, explicit_records):
        assert default.payoff == pytest.approx(explicit.payoff)


def test_multiplier_two_doubles_pr_only():
    records = generate_monthly_bvg_cashflow_records_for_state(
        PORTFOLIO, REPORTING_YEAR, contribution_multiplier=2.0
    )
    pr_act40 = [r.payoff for r in records if r.contractId == "ACT_40"]
    pr_act55 = [r.payoff for r in records if r.contractId == "ACT_55"]
    rp_ret70 = [r.payoff for r in records if r.contractId == "RET_70"]
    for payoff in pr_act40:
        assert payoff == pytest.approx(59275.0 * 2.0 / 12)
    for payoff in pr_act55:
        assert payoff == pytest.approx(18508.5 * 2.0 / 12)
    for payoff in rp_ret70:
        assert payoff == pytest.approx(-150_000.0 / 12)


def test_multiplier_zero_zeros_pr_only():
    records = generate_monthly_bvg_cashflow_records_for_state(
        PORTFOLIO, REPORTING_YEAR, contribution_multiplier=0.0
    )
    pr_payoffs = [r.payoff for r in records if r.type == "PR"]
    rp_payoffs = [r.payoff for r in records if r.type == "RP"]
    assert pr_payoffs
    for payoff in pr_payoffs:
        assert payoff == pytest.approx(0.0)
    for payoff in rp_payoffs:
        assert payoff == pytest.approx(-150_000.0 / 12)


# ---------------------------------------------------------------------------
# G. Invalid inputs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_portfolio", [None, "not a portfolio", 42, {"k": 1}])
def test_invalid_portfolio_type_raises(bad_portfolio):
    with pytest.raises(TypeError):
        generate_monthly_bvg_cashflow_records_for_state(
            bad_portfolio, REPORTING_YEAR
        )


@pytest.mark.parametrize("bad_year", [True, False, 2026.5, "2026", None])
def test_invalid_reporting_year_type_raises(bad_year):
    with pytest.raises(TypeError):
        generate_monthly_bvg_cashflow_records_for_state(PORTFOLIO, bad_year)


def test_negative_reporting_year_raises():
    with pytest.raises(ValueError):
        generate_monthly_bvg_cashflow_records_for_state(PORTFOLIO, -1)


@pytest.mark.parametrize("bad_multiplier", [True, False, "x", None])
def test_invalid_multiplier_type_raises(bad_multiplier):
    with pytest.raises(TypeError):
        generate_monthly_bvg_cashflow_records_for_state(
            PORTFOLIO, REPORTING_YEAR, contribution_multiplier=bad_multiplier
        )


def test_nan_multiplier_raises():
    with pytest.raises(ValueError):
        generate_monthly_bvg_cashflow_records_for_state(
            PORTFOLIO, REPORTING_YEAR, contribution_multiplier=math.nan
        )


def test_negative_multiplier_raises():
    with pytest.raises(ValueError):
        generate_monthly_bvg_cashflow_records_for_state(
            PORTFOLIO, REPORTING_YEAR, contribution_multiplier=-0.5
        )


def test_invalid_inputs_propagate_to_dataframe_helper():
    with pytest.raises(TypeError):
        generate_monthly_bvg_cashflow_dataframe_for_state(
            PORTFOLIO, REPORTING_YEAR, contribution_multiplier="bad"
        )
    with pytest.raises(ValueError):
        generate_monthly_bvg_cashflow_dataframe_for_state(
            PORTFOLIO, REPORTING_YEAR, contribution_multiplier=-1.0
        )


# ---------------------------------------------------------------------------
# H. Leap year
# ---------------------------------------------------------------------------


def test_leap_year_february_uses_29th():
    records = generate_monthly_bvg_cashflow_records_for_state(PORTFOLIO, 2028)
    february_records = [r for r in records if r.time.month == 2]
    assert february_records
    for record in february_records:
        assert record.time == pd.Timestamp("2028-02-29")


# ---------------------------------------------------------------------------
# I. Immutability
# ---------------------------------------------------------------------------


def test_generator_does_not_mutate_inputs():
    portfolio = BVGPortfolioState(
        active_cohorts=(ACT_40, ACT_55),
        retired_cohorts=(RET_70,),
    )
    snap_year = portfolio.projection_year
    snap_active_ages = tuple(c.age for c in portfolio.active_cohorts)
    snap_active_capital = tuple(
        c.capital_active_per_person for c in portfolio.active_cohorts
    )
    snap_retired_ages = tuple(c.age for c in portfolio.retired_cohorts)
    snap_retired_capital = tuple(
        c.capital_rente_per_person for c in portfolio.retired_cohorts
    )

    generate_monthly_bvg_cashflow_records_for_state(portfolio, REPORTING_YEAR)
    generate_monthly_bvg_cashflow_dataframe_for_state(portfolio, REPORTING_YEAR)

    assert portfolio.projection_year == snap_year
    assert tuple(c.age for c in portfolio.active_cohorts) == snap_active_ages
    assert (
        tuple(c.capital_active_per_person for c in portfolio.active_cohorts)
        == snap_active_capital
    )
    assert tuple(c.age for c in portfolio.retired_cohorts) == snap_retired_ages
    assert (
        tuple(c.capital_rente_per_person for c in portfolio.retired_cohorts)
        == snap_retired_capital
    )


# ---------------------------------------------------------------------------
# J. Chronological ordering
# ---------------------------------------------------------------------------


def test_dataframe_time_column_is_monotonic_increasing():
    df = generate_monthly_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, REPORTING_YEAR
    )
    assert df["time"].is_monotonic_increasing


def test_within_each_month_actives_precede_retirees():
    df = generate_monthly_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, REPORTING_YEAR
    )
    for month_end, group in df.groupby("time", sort=False):
        types = list(group["type"])
        # In each month: PR rows first, RP rows after.
        assert types == ["PR", "PR", "RP"], (
            f"unexpected ordering at {month_end}: {types}"
        )
