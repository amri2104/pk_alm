import math

import pandas as pd
import pytest
from pk_alm.bvg_liability_engine.domain_models.cohorts import ActiveCohort, RetiredCohort
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.bvg_liability_engine.pension_logic.valuation import (
    VALUATION_COLUMNS,
    BVGValuationSnapshot,
    validate_valuation_dataframe,
    valuation_snapshots_to_dataframe,
    value_portfolio_state,
    value_portfolio_states,
)

RATE = 0.0176


# ---------------------------------------------------------------------------
# Shared cohort builders
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


def _valid_snapshot_kwargs(**overrides) -> dict:
    base = dict(
        projection_year=0,
        active_count_total=10,
        retired_count_total=5,
        member_count_total=15,
        total_capital_active=1_000_000.0,
        total_capital_rente=500_000.0,
        retiree_obligation_pv=600_000.0,
        pensionierungsverlust=100_000.0,
        total_stage1_liability=1_600_000.0,
        technical_interest_rate=RATE,
        valuation_terminal_age=90,
        currency="CHF",
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# A. Standard portfolio valuation
# ---------------------------------------------------------------------------


def test_standard_portfolio_snapshot_values():
    snap = value_portfolio_state(_standard_portfolio(), RATE)

    assert snap.projection_year == 0
    assert snap.active_count_total == 13
    assert snap.retired_count_total == 5
    assert snap.member_count_total == 18
    assert snap.total_capital_active == pytest.approx(2_100_000.0)
    assert snap.total_capital_rente == pytest.approx(2_250_000.0)
    assert snap.retiree_obligation_pv == pytest.approx(2_554_667.3903511222)
    assert snap.pensionierungsverlust == pytest.approx(304_667.39035112225)
    assert snap.total_stage1_liability == pytest.approx(4_654_667.390351122)
    assert snap.technical_interest_rate == pytest.approx(RATE)
    assert snap.valuation_terminal_age == 90
    assert snap.currency == "CHF"


# ---------------------------------------------------------------------------
# B. Empty portfolio
# ---------------------------------------------------------------------------


def test_empty_portfolio_snapshot_values():
    snap = value_portfolio_state(BVGPortfolioState(), RATE)

    assert snap.projection_year == 0
    assert snap.active_count_total == 0
    assert snap.retired_count_total == 0
    assert snap.member_count_total == 0
    assert snap.total_capital_active == pytest.approx(0.0)
    assert snap.total_capital_rente == pytest.approx(0.0)
    assert snap.retiree_obligation_pv == pytest.approx(0.0)
    assert snap.pensionierungsverlust == pytest.approx(0.0)
    assert snap.total_stage1_liability == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# C. Active-only portfolio
# ---------------------------------------------------------------------------


def test_active_only_portfolio():
    portfolio = BVGPortfolioState(active_cohorts=(_act_40(),))
    snap = value_portfolio_state(portfolio, RATE)

    assert snap.retiree_obligation_pv == pytest.approx(0.0)
    assert snap.total_stage1_liability == pytest.approx(snap.total_capital_active)
    assert snap.pensionierungsverlust == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# D. Retired-only portfolio
# ---------------------------------------------------------------------------


def test_retired_only_portfolio():
    portfolio = BVGPortfolioState(retired_cohorts=(_ret_70(),))
    snap = value_portfolio_state(portfolio, RATE)

    assert snap.total_capital_active == pytest.approx(0.0)
    assert snap.total_stage1_liability == pytest.approx(snap.retiree_obligation_pv)


# ---------------------------------------------------------------------------
# E. Terminal age boundary
# ---------------------------------------------------------------------------


def test_retiree_at_terminal_age_has_zero_pv():
    ret_90 = RetiredCohort(
        cohort_id="RET_90",
        age=90,
        count=1,
        annual_pension_per_person=30000,
        capital_rente_per_person=100000,
    )
    portfolio = BVGPortfolioState(retired_cohorts=(ret_90,))
    snap = value_portfolio_state(portfolio, RATE, valuation_terminal_age=90)

    assert snap.retiree_obligation_pv == pytest.approx(0.0)
    assert snap.pensionierungsverlust == pytest.approx(-100_000.0)
    assert snap.total_stage1_liability == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# F. Snapshot to_dict and DataFrame helpers
# ---------------------------------------------------------------------------


def test_snapshot_to_dict_keys_in_order():
    snap = value_portfolio_state(_standard_portfolio(), RATE)
    assert list(snap.to_dict().keys()) == list(VALUATION_COLUMNS)


def test_snapshots_to_dataframe_shape_and_columns():
    snap = value_portfolio_state(_standard_portfolio(), RATE)
    df = valuation_snapshots_to_dataframe([snap])
    assert df.shape == (1, len(VALUATION_COLUMNS))
    assert list(df.columns) == list(VALUATION_COLUMNS)
    assert validate_valuation_dataframe(df) is True


def test_empty_snapshots_returns_empty_dataframe_with_columns():
    df = valuation_snapshots_to_dataframe([])
    assert df.empty
    assert list(df.columns) == list(VALUATION_COLUMNS)


# ---------------------------------------------------------------------------
# G. value_portfolio_states for a trajectory
# ---------------------------------------------------------------------------


def test_value_portfolio_states_trajectory():
    a0 = ActiveCohort(
        cohort_id="ACT_X",
        age=40,
        count=1,
        gross_salary_per_person=85000,
        capital_active_per_person=100000,
    )
    a1 = ActiveCohort(
        cohort_id="ACT_X",
        age=41,
        count=1,
        gross_salary_per_person=85000,
        capital_active_per_person=110000,
    )
    state0 = BVGPortfolioState(projection_year=0, active_cohorts=(a0,))
    state1 = BVGPortfolioState(projection_year=1, active_cohorts=(a1,))

    df = value_portfolio_states((state0, state1), RATE)

    assert df.shape == (2, len(VALUATION_COLUMNS))
    assert list(df["projection_year"]) == [0, 1]
    assert list(df["total_stage1_liability"]) == [100000.0, 110000.0]
    assert validate_valuation_dataframe(df) is True


# ---------------------------------------------------------------------------
# H. Immutability
# ---------------------------------------------------------------------------


def test_snapshot_is_frozen():
    snap = value_portfolio_state(_standard_portfolio(), RATE)
    with pytest.raises(Exception):
        snap.projection_year = 99  # type: ignore[misc]


def test_valuation_does_not_mutate_portfolio():
    portfolio = _standard_portfolio()
    snap_active_caps = tuple(
        c.capital_active_per_person for c in portfolio.active_cohorts
    )
    snap_retired_caps = tuple(
        c.capital_rente_per_person for c in portfolio.retired_cohorts
    )
    value_portfolio_state(portfolio, RATE)
    assert (
        tuple(c.capital_active_per_person for c in portfolio.active_cohorts)
        == snap_active_caps
    )
    assert (
        tuple(c.capital_rente_per_person for c in portfolio.retired_cohorts)
        == snap_retired_caps
    )


# ---------------------------------------------------------------------------
# I. Invalid inputs for value_portfolio_state
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [None, "x", {"k": 1}])
def test_value_portfolio_state_bad_portfolio_raises(bad):
    with pytest.raises(TypeError):
        value_portfolio_state(bad, RATE)


@pytest.mark.parametrize("bad", [True, "x", None])
def test_technical_interest_rate_bad_type_raises(bad):
    with pytest.raises(TypeError):
        value_portfolio_state(_standard_portfolio(), bad)


def test_technical_interest_rate_minus_one_raises():
    with pytest.raises(ValueError):
        value_portfolio_state(_standard_portfolio(), -1.0)


def test_technical_interest_rate_below_minus_one_raises():
    with pytest.raises(ValueError):
        value_portfolio_state(_standard_portfolio(), -1.5)


def test_technical_interest_rate_nan_raises():
    with pytest.raises(ValueError):
        value_portfolio_state(_standard_portfolio(), math.nan)


@pytest.mark.parametrize("bad", [True, 90.0, "90"])
def test_valuation_terminal_age_bad_type_raises(bad):
    with pytest.raises(TypeError):
        value_portfolio_state(
            _standard_portfolio(), RATE, valuation_terminal_age=bad
        )


def test_valuation_terminal_age_negative_raises():
    with pytest.raises(ValueError):
        value_portfolio_state(
            _standard_portfolio(), RATE, valuation_terminal_age=-1
        )


@pytest.mark.parametrize("bad", ["", "   "])
def test_currency_invalid_raises(bad):
    with pytest.raises(ValueError):
        value_portfolio_state(_standard_portfolio(), RATE, currency=bad)


def test_currency_non_string_raises():
    with pytest.raises(ValueError):
        value_portfolio_state(_standard_portfolio(), RATE, currency=42)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# J. Invalid inputs for valuation_snapshots_to_dataframe
# ---------------------------------------------------------------------------


def test_snapshots_to_df_none_raises():
    with pytest.raises(TypeError):
        valuation_snapshots_to_dataframe(None)  # type: ignore[arg-type]


def test_snapshots_to_df_string_raises():
    with pytest.raises(TypeError):
        valuation_snapshots_to_dataframe("not a list")  # type: ignore[arg-type]


def test_snapshots_to_df_wrong_item_type_raises():
    with pytest.raises(TypeError):
        valuation_snapshots_to_dataframe([{"k": 1}])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# K. Invalid DataFrame validation
# ---------------------------------------------------------------------------


def _valid_df():
    snap = value_portfolio_state(_standard_portfolio(), RATE)
    return valuation_snapshots_to_dataframe([snap])


def test_validate_non_dataframe_raises():
    with pytest.raises(TypeError):
        validate_valuation_dataframe("not a df")  # type: ignore[arg-type]


def test_validate_missing_column_raises():
    df = _valid_df().drop(columns=["currency"])
    with pytest.raises(ValueError, match="missing required columns"):
        validate_valuation_dataframe(df)


def test_validate_wrong_column_order_raises():
    df = _valid_df()
    reordered = df[list(reversed(VALUATION_COLUMNS))]
    with pytest.raises(ValueError, match="columns must be in order"):
        validate_valuation_dataframe(reordered)


def _set_value(df, column, value):
    df = df.copy()
    df[column] = pd.Series([value], dtype=object)
    return df


@pytest.mark.parametrize(
    "bad", [math.nan, None, pd.NA, pd.NaT]
)
def test_validate_missing_value_in_required_column_raises(bad):
    df = _set_value(_valid_df(), "total_capital_active", bad)
    with pytest.raises(ValueError, match="must not contain NaN"):
        validate_valuation_dataframe(df)


def test_validate_negative_count_raises():
    df = _set_value(_valid_df(), "active_count_total", -1)
    with pytest.raises(ValueError, match="active_count_total"):
        validate_valuation_dataframe(df)


def test_validate_inconsistent_member_count_raises():
    df = _valid_df().copy()
    df.loc[0, "member_count_total"] = df.loc[0, "active_count_total"] + 999
    with pytest.raises(ValueError, match="member_count_total"):
        validate_valuation_dataframe(df)


def test_validate_negative_capital_active_raises():
    df = _set_value(_valid_df(), "total_capital_active", -1.0)
    with pytest.raises(ValueError, match="total_capital_active"):
        validate_valuation_dataframe(df)


def test_validate_invalid_technical_rate_raises():
    df = _set_value(_valid_df(), "technical_interest_rate", -1.5)
    with pytest.raises(ValueError, match="technical_interest_rate"):
        validate_valuation_dataframe(df)


def test_validate_empty_currency_raises():
    df = _set_value(_valid_df(), "currency", "")
    with pytest.raises(ValueError, match="currency"):
        validate_valuation_dataframe(df)


def test_validate_inconsistent_total_stage1_liability_raises():
    df = _valid_df().copy()
    df.loc[0, "total_stage1_liability"] = (
        df.loc[0, "total_capital_active"] + df.loc[0, "retiree_obligation_pv"] + 999
    )
    with pytest.raises(ValueError, match="total_stage1_liability"):
        validate_valuation_dataframe(df)


# ---------------------------------------------------------------------------
# L. Invalid BVGValuationSnapshot construction
# ---------------------------------------------------------------------------


def test_snapshot_wrong_member_count_raises():
    with pytest.raises(ValueError, match="member_count_total"):
        BVGValuationSnapshot(
            **_valid_snapshot_kwargs(member_count_total=999)
        )


def test_snapshot_wrong_total_stage1_liability_raises():
    with pytest.raises(ValueError, match="total_stage1_liability"):
        BVGValuationSnapshot(
            **_valid_snapshot_kwargs(total_stage1_liability=999_999.0)
        )


def test_snapshot_negative_capital_rente_raises():
    with pytest.raises(ValueError, match="total_capital_rente"):
        BVGValuationSnapshot(**_valid_snapshot_kwargs(total_capital_rente=-1.0))


def test_snapshot_allows_negative_pensionierungsverlust():
    # Build a self-consistent snapshot where pensionierungsverlust is negative.
    snap = BVGValuationSnapshot(
        **_valid_snapshot_kwargs(pensionierungsverlust=-50_000.0)
    )
    assert snap.pensionierungsverlust == pytest.approx(-50_000.0)


# ---------------------------------------------------------------------------
# M. Float tolerance
# ---------------------------------------------------------------------------


def test_snapshot_construction_within_tolerance_succeeds():
    # diff < 1e-5
    snap = BVGValuationSnapshot(
        **_valid_snapshot_kwargs(total_stage1_liability=1_600_000.0 + 1e-7)
    )
    assert snap is not None


def test_snapshot_construction_outside_tolerance_raises():
    # diff far above 1e-5
    with pytest.raises(ValueError, match="total_stage1_liability"):
        BVGValuationSnapshot(
            **_valid_snapshot_kwargs(total_stage1_liability=1_600_000.0 + 1.0)
        )
