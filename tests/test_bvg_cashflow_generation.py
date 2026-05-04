import math

import pandas as pd
import pytest
from pk_alm.bvg_liability_engine.pension_logic.cashflow_generation import (
    generate_bvg_cashflow_dataframe_for_state,
    generate_bvg_cashflow_records_for_state,
)
from pk_alm.bvg_liability_engine.domain_models.cohorts import ActiveCohort, RetiredCohort
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.cashflows.schema import CASHFLOW_COLUMNS, validate_cashflow_dataframe

EVENT_DATE = "2026-12-31"
EVENT_TS = pd.Timestamp(EVENT_DATE)


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
# A. Standard portfolio cashflow records
# ---------------------------------------------------------------------------


def test_records_returns_tuple_of_three():
    records = generate_bvg_cashflow_records_for_state(PORTFOLIO, EVENT_DATE)
    assert isinstance(records, tuple)
    assert len(records) == 3


def test_record_act40_fields():
    records = generate_bvg_cashflow_records_for_state(PORTFOLIO, EVENT_DATE)
    r = records[0]
    assert r.contractId == "ACT_40"
    assert r.type == "PR"
    assert r.payoff == pytest.approx(59275.0)
    assert r.nominalValue == pytest.approx(1_200_000.0)
    assert r.source == "BVG"
    assert r.currency == "CHF"


def test_record_act55_fields():
    records = generate_bvg_cashflow_records_for_state(PORTFOLIO, EVENT_DATE)
    r = records[1]
    assert r.contractId == "ACT_55"
    assert r.type == "PR"
    assert r.payoff == pytest.approx(18508.5)
    assert r.nominalValue == pytest.approx(900_000.0)
    assert r.source == "BVG"


def test_record_ret70_fields():
    records = generate_bvg_cashflow_records_for_state(PORTFOLIO, EVENT_DATE)
    r = records[2]
    assert r.contractId == "RET_70"
    assert r.type == "RP"
    assert r.payoff == pytest.approx(-150_000.0)
    assert r.nominalValue == pytest.approx(2_250_000.0)
    assert r.source == "BVG"


# ---------------------------------------------------------------------------
# B. Standard portfolio cashflow DataFrame
# ---------------------------------------------------------------------------


def test_dataframe_shape_and_columns():
    df = generate_bvg_cashflow_dataframe_for_state(PORTFOLIO, EVENT_DATE)
    assert df.shape == (3, len(CASHFLOW_COLUMNS))
    assert list(df.columns) == list(CASHFLOW_COLUMNS)


def test_dataframe_validates():
    df = generate_bvg_cashflow_dataframe_for_state(PORTFOLIO, EVENT_DATE)
    assert validate_cashflow_dataframe(df) is True


def test_dataframe_payoff_sum():
    df = generate_bvg_cashflow_dataframe_for_state(PORTFOLIO, EVENT_DATE)
    # 59275.0 + 18508.5 - 150000.0 = -72216.5
    assert df["payoff"].sum() == pytest.approx(-72216.5)


def test_dataframe_all_sources_bvg():
    df = generate_bvg_cashflow_dataframe_for_state(PORTFOLIO, EVENT_DATE)
    assert (df["source"] == "BVG").all()


def test_dataframe_active_rows_positive():
    df = generate_bvg_cashflow_dataframe_for_state(PORTFOLIO, EVENT_DATE)
    active_rows = df[df["type"] == "PR"]
    assert (active_rows["payoff"] > 0).all()


def test_dataframe_retired_row_negative():
    df = generate_bvg_cashflow_dataframe_for_state(PORTFOLIO, EVENT_DATE)
    retired_rows = df[df["type"] == "RP"]
    assert (retired_rows["payoff"] < 0).all()


# ---------------------------------------------------------------------------
# C. Empty portfolio
# ---------------------------------------------------------------------------


def test_records_empty_portfolio():
    records = generate_bvg_cashflow_records_for_state(BVGPortfolioState(), EVENT_DATE)
    assert records == ()


def test_dataframe_empty_portfolio():
    df = generate_bvg_cashflow_dataframe_for_state(BVGPortfolioState(), EVENT_DATE)
    assert df.empty
    assert list(df.columns) == list(CASHFLOW_COLUMNS)
    assert validate_cashflow_dataframe(df) is True


# ---------------------------------------------------------------------------
# D. Event date normalization
# ---------------------------------------------------------------------------


def test_all_records_share_normalized_timestamp():
    records = generate_bvg_cashflow_records_for_state(PORTFOLIO, EVENT_DATE)
    for r in records:
        assert r.time == EVENT_TS
        assert isinstance(r.time, pd.Timestamp)


# ---------------------------------------------------------------------------
# E. Ordering test
# ---------------------------------------------------------------------------


def test_record_order():
    records = generate_bvg_cashflow_records_for_state(PORTFOLIO, EVENT_DATE)
    assert tuple(r.contractId for r in records) == ("ACT_40", "ACT_55", "RET_70")
    assert tuple(r.type for r in records) == ("PR", "PR", "RP")


def test_dataframe_order():
    df = generate_bvg_cashflow_dataframe_for_state(PORTFOLIO, EVENT_DATE)
    assert list(df["contractId"]) == ["ACT_40", "ACT_55", "RET_70"]


# ---------------------------------------------------------------------------
# F. Invalid portfolio input
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_portfolio", [None, "not a portfolio", 42, {"k": 1}])
def test_records_invalid_portfolio_raises(bad_portfolio):
    with pytest.raises(TypeError):
        generate_bvg_cashflow_records_for_state(bad_portfolio, EVENT_DATE)


@pytest.mark.parametrize("bad_portfolio", [None, "not a portfolio", 42, {"k": 1}])
def test_dataframe_invalid_portfolio_raises(bad_portfolio):
    with pytest.raises(TypeError):
        generate_bvg_cashflow_dataframe_for_state(bad_portfolio, EVENT_DATE)


# ---------------------------------------------------------------------------
# G. Invalid event date
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_date", [None, "not-a-date"])
def test_records_invalid_event_date_raises(bad_date):
    with pytest.raises(ValueError):
        generate_bvg_cashflow_records_for_state(PORTFOLIO, bad_date)


@pytest.mark.parametrize("bad_date", [None, "not-a-date"])
def test_dataframe_invalid_event_date_raises(bad_date):
    with pytest.raises(ValueError):
        generate_bvg_cashflow_dataframe_for_state(PORTFOLIO, bad_date)


# ---------------------------------------------------------------------------
# H. No mutation
# ---------------------------------------------------------------------------


def test_no_mutation_of_portfolio_or_cohorts():
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

    generate_bvg_cashflow_records_for_state(portfolio, EVENT_DATE)
    generate_bvg_cashflow_dataframe_for_state(portfolio, EVENT_DATE)

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
# I. contribution_multiplier
# ---------------------------------------------------------------------------


def test_default_multiplier_one():
    default_records = generate_bvg_cashflow_records_for_state(PORTFOLIO, EVENT_DATE)
    explicit_records = generate_bvg_cashflow_records_for_state(
        PORTFOLIO, EVENT_DATE, contribution_multiplier=1.0
    )
    for d, e in zip(default_records, explicit_records):
        assert d.payoff == pytest.approx(e.payoff)


def test_multiplier_two_doubles_active_only():
    records = generate_bvg_cashflow_records_for_state(
        PORTFOLIO, EVENT_DATE, contribution_multiplier=2.0
    )
    # Active payoffs doubled
    assert records[0].payoff == pytest.approx(59275.0 * 2)
    assert records[1].payoff == pytest.approx(18508.5 * 2)
    # Retired payoff unchanged
    assert records[2].payoff == pytest.approx(-150_000.0)


def test_multiplier_zero_zeros_active_only():
    records = generate_bvg_cashflow_records_for_state(
        PORTFOLIO, EVENT_DATE, contribution_multiplier=0.0
    )
    assert records[0].payoff == pytest.approx(0.0)
    assert records[1].payoff == pytest.approx(0.0)
    assert records[2].payoff == pytest.approx(-150_000.0)


def test_multiplier_propagates_to_dataframe():
    df = generate_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, EVENT_DATE, contribution_multiplier=2.0
    )
    # Sum: 2 * 59275 + 2 * 18508.5 - 150000 = 155567 - 150000 = 5567
    assert df["payoff"].sum() == pytest.approx(5567.0)


@pytest.mark.parametrize("bad", ["x", None, True])
def test_multiplier_invalid_type_raises(bad):
    with pytest.raises(TypeError):
        generate_bvg_cashflow_records_for_state(
            PORTFOLIO, EVENT_DATE, contribution_multiplier=bad
        )


def test_multiplier_negative_raises():
    with pytest.raises(ValueError):
        generate_bvg_cashflow_records_for_state(
            PORTFOLIO, EVENT_DATE, contribution_multiplier=-0.5
        )


def test_multiplier_nan_raises():
    with pytest.raises(ValueError):
        generate_bvg_cashflow_records_for_state(
            PORTFOLIO, EVENT_DATE, contribution_multiplier=math.nan
        )


def test_multiplier_invalid_propagates_to_dataframe():
    with pytest.raises(ValueError):
        generate_bvg_cashflow_dataframe_for_state(
            PORTFOLIO, EVENT_DATE, contribution_multiplier=-1.0
        )
    with pytest.raises(TypeError):
        generate_bvg_cashflow_dataframe_for_state(
            PORTFOLIO, EVENT_DATE, contribution_multiplier="bad"
        )
