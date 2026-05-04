import math

import numpy as np
import pandas as pd
import pytest
from pk_alm.alm_analytics_engine.cashflows import (
    ANNUAL_CASHFLOW_COLUMNS,
    find_liquidity_inflection_year,
    summarize_cashflows_by_year,
    validate_annual_cashflow_dataframe,
)
from pk_alm.cashflows.schema import (
    CASHFLOW_COLUMNS,
    CashflowRecord,
    cashflow_records_to_dataframe,
)


def _rec(time, type_, payoff, currency="CHF", contract_id="X"):
    return CashflowRecord(
        contractId=contract_id,
        time=time,
        type=type_,
        payoff=payoff,
        nominalValue=0.0,
        currency=currency,
        source="BVG",
    )


def _standard_two_year_cashflows():
    return cashflow_records_to_dataframe(
        [
            _rec("2026-12-31", "PR", 100.0),
            _rec("2026-12-31", "RP", -80.0),
            _rec("2026-12-31", "KA", -50.0),
            _rec("2026-12-31", "OTHER", 10.0),
            _rec("2027-12-31", "PR", 70.0),
            _rec("2027-12-31", "RP", -90.0),
        ]
    )


# ---------------------------------------------------------------------------
# A. Standard two-year summary
# ---------------------------------------------------------------------------


def test_standard_summary_shape_and_columns():
    summary = summarize_cashflows_by_year(_standard_two_year_cashflows())
    assert summary.shape == (2, len(ANNUAL_CASHFLOW_COLUMNS))
    assert list(summary.columns) == list(ANNUAL_CASHFLOW_COLUMNS)
    assert validate_annual_cashflow_dataframe(summary) is True


def test_standard_summary_2026_row():
    summary = summarize_cashflows_by_year(_standard_two_year_cashflows())
    row = summary.iloc[0]
    assert int(row["reporting_year"]) == 2026
    assert row["contribution_cashflow"] == pytest.approx(100.0)
    assert row["pension_payment_cashflow"] == pytest.approx(-80.0)
    assert row["capital_withdrawal_cashflow"] == pytest.approx(-50.0)
    assert row["other_cashflow"] == pytest.approx(10.0)
    assert row["net_cashflow"] == pytest.approx(-20.0)
    assert row["structural_net_cashflow"] == pytest.approx(20.0)
    assert row["cumulative_net_cashflow"] == pytest.approx(-20.0)
    assert row["cumulative_structural_net_cashflow"] == pytest.approx(20.0)
    assert row["currency"] == "CHF"


def test_standard_summary_2027_row():
    summary = summarize_cashflows_by_year(_standard_two_year_cashflows())
    row = summary.iloc[1]
    assert int(row["reporting_year"]) == 2027
    assert row["contribution_cashflow"] == pytest.approx(70.0)
    assert row["pension_payment_cashflow"] == pytest.approx(-90.0)
    assert row["capital_withdrawal_cashflow"] == pytest.approx(0.0)
    assert row["other_cashflow"] == pytest.approx(0.0)
    assert row["net_cashflow"] == pytest.approx(-20.0)
    assert row["structural_net_cashflow"] == pytest.approx(-20.0)
    assert row["cumulative_net_cashflow"] == pytest.approx(-40.0)
    assert row["cumulative_structural_net_cashflow"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# B. Empty input
# ---------------------------------------------------------------------------


def test_empty_summary_returns_empty_with_columns():
    empty_in = cashflow_records_to_dataframe([])
    out = summarize_cashflows_by_year(empty_in)
    assert out.empty
    assert list(out.columns) == list(ANNUAL_CASHFLOW_COLUMNS)
    assert validate_annual_cashflow_dataframe(out) is True
    assert find_liquidity_inflection_year(out) is None


# ---------------------------------------------------------------------------
# C. Order independence
# ---------------------------------------------------------------------------


def test_order_independence_sorted_by_year_with_correct_cumsum():
    out_of_order = cashflow_records_to_dataframe(
        [
            _rec("2027-12-31", "RP", -90.0),
            _rec("2026-12-31", "PR", 100.0),
            _rec("2027-12-31", "PR", 70.0),
            _rec("2026-12-31", "KA", -50.0),
            _rec("2026-12-31", "RP", -80.0),
            _rec("2026-12-31", "OTHER", 10.0),
        ]
    )
    summary = summarize_cashflows_by_year(out_of_order)
    assert list(summary["reporting_year"]) == [2026, 2027]
    assert list(summary["cumulative_net_cashflow"]) == pytest.approx([-20.0, -40.0])


# ---------------------------------------------------------------------------
# D. Multiple rows same year
# ---------------------------------------------------------------------------


def test_multiple_rows_same_year_aggregate_correctly():
    df = cashflow_records_to_dataframe(
        [
            _rec("2026-12-31", "PR", 50.0),
            _rec("2026-12-31", "PR", 50.0),  # second PR same year
            _rec("2026-12-31", "RP", -40.0),
            _rec("2026-12-31", "RP", -40.0),
            _rec("2026-12-31", "KA", -25.0),
            _rec("2026-12-31", "KA", -25.0),
        ]
    )
    summary = summarize_cashflows_by_year(df)
    row = summary.iloc[0]
    assert row["contribution_cashflow"] == pytest.approx(100.0)
    assert row["pension_payment_cashflow"] == pytest.approx(-80.0)
    assert row["capital_withdrawal_cashflow"] == pytest.approx(-50.0)


# ---------------------------------------------------------------------------
# E. Contribution multiplier already in payoff
# ---------------------------------------------------------------------------


def test_analytics_uses_payoff_as_is():
    df = cashflow_records_to_dataframe([_rec("2026-12-31", "PR", 140.0)])
    summary = summarize_cashflows_by_year(df)
    assert summary.iloc[0]["contribution_cashflow"] == pytest.approx(140.0)


# ---------------------------------------------------------------------------
# F. Liquidity inflection
# ---------------------------------------------------------------------------


def test_liquidity_inflection_structural_returns_2027():
    summary = summarize_cashflows_by_year(_standard_two_year_cashflows())
    assert find_liquidity_inflection_year(summary, use_structural=True) == 2027


def test_liquidity_inflection_net_returns_2026():
    summary = summarize_cashflows_by_year(_standard_two_year_cashflows())
    assert find_liquidity_inflection_year(summary, use_structural=False) == 2026


# ---------------------------------------------------------------------------
# G. No inflection
# ---------------------------------------------------------------------------


def test_no_inflection_returns_none():
    df = cashflow_records_to_dataframe(
        [
            _rec("2026-12-31", "PR", 200.0),
            _rec("2026-12-31", "RP", -100.0),
            _rec("2027-12-31", "PR", 150.0),
            _rec("2027-12-31", "RP", -120.0),
        ]
    )
    summary = summarize_cashflows_by_year(df)
    assert find_liquidity_inflection_year(summary) is None
    assert find_liquidity_inflection_year(summary, use_structural=False) is None


# ---------------------------------------------------------------------------
# H. Multiple currencies rejected
# ---------------------------------------------------------------------------


def test_multiple_currencies_raises():
    df = cashflow_records_to_dataframe(
        [
            _rec("2026-12-31", "PR", 100.0, currency="CHF"),
            _rec("2026-12-31", "PR", 100.0, currency="EUR"),
        ]
    )
    with pytest.raises(ValueError, match="one currency"):
        summarize_cashflows_by_year(df)


# ---------------------------------------------------------------------------
# I. Invalid inputs for summarize_cashflows_by_year
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [None, "x", [1, 2, 3]])
def test_summarize_bad_input_type_raises(bad):
    with pytest.raises(TypeError):
        summarize_cashflows_by_year(bad)


def test_summarize_missing_schema_column_raises():
    df = _standard_two_year_cashflows().drop(columns=["payoff"])
    with pytest.raises(ValueError):
        summarize_cashflows_by_year(df)


def test_summarize_wrong_schema_column_order_raises():
    df = _standard_two_year_cashflows()
    reordered = df[list(reversed(CASHFLOW_COLUMNS))]
    with pytest.raises(ValueError):
        summarize_cashflows_by_year(reordered)


def test_summarize_invalid_payoff_raises():
    df = _standard_two_year_cashflows().copy()
    df["payoff"] = pd.Series([math.nan] * len(df), dtype=object)
    with pytest.raises(ValueError):
        summarize_cashflows_by_year(df)


# ---------------------------------------------------------------------------
# J. Invalid annual analytics validation
# ---------------------------------------------------------------------------


def _valid_summary():
    return summarize_cashflows_by_year(_standard_two_year_cashflows())


def test_validate_non_dataframe_raises():
    with pytest.raises(TypeError):
        validate_annual_cashflow_dataframe("not a df")  # type: ignore[arg-type]


def test_validate_missing_column_raises():
    df = _valid_summary().drop(columns=["currency"])
    with pytest.raises(ValueError, match="missing required columns"):
        validate_annual_cashflow_dataframe(df)


def test_validate_wrong_column_order_raises():
    df = _valid_summary()
    reordered = df[list(reversed(ANNUAL_CASHFLOW_COLUMNS))]
    with pytest.raises(ValueError, match="columns must be in order"):
        validate_annual_cashflow_dataframe(reordered)


def _set_value(df, column, value):
    df = df.copy()
    df[column] = pd.Series([value, value], dtype=object)
    return df


@pytest.mark.parametrize("bad", [math.nan, None, pd.NA, pd.NaT])
def test_validate_missing_value_in_required_column_raises(bad):
    df = _set_value(_valid_summary(), "contribution_cashflow", bad)
    with pytest.raises(ValueError, match="must not contain NaN"):
        validate_annual_cashflow_dataframe(df)


def test_validate_negative_reporting_year_raises():
    df = _valid_summary().copy()
    df.loc[0, "reporting_year"] = -1
    with pytest.raises(ValueError, match="reporting_year"):
        validate_annual_cashflow_dataframe(df)


def test_validate_invalid_currency_raises():
    df = _set_value(_valid_summary(), "currency", "")
    with pytest.raises(ValueError, match="currency"):
        validate_annual_cashflow_dataframe(df)


def test_validate_inconsistent_net_raises():
    df = _valid_summary().copy()
    df.loc[0, "net_cashflow"] = df.loc[0, "net_cashflow"] + 999.0
    with pytest.raises(ValueError, match="net_cashflow"):
        validate_annual_cashflow_dataframe(df)


def test_validate_inconsistent_structural_raises():
    df = _valid_summary().copy()
    df.loc[0, "structural_net_cashflow"] = df.loc[0, "structural_net_cashflow"] + 999.0
    with pytest.raises(ValueError, match="structural_net_cashflow"):
        validate_annual_cashflow_dataframe(df)


# ---------------------------------------------------------------------------
# K. Invalid liquidity-inflection input
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [None, 1, "x"])
def test_inflection_use_structural_must_be_bool(bad):
    summary = _valid_summary()
    with pytest.raises(TypeError):
        find_liquidity_inflection_year(summary, use_structural=bad)


def test_inflection_non_dataframe_raises():
    with pytest.raises(TypeError):
        find_liquidity_inflection_year("not a df")  # type: ignore[arg-type]


def test_inflection_invalid_annual_df_raises():
    df = _valid_summary().drop(columns=["currency"])
    with pytest.raises(ValueError):
        find_liquidity_inflection_year(df)


# ---------------------------------------------------------------------------
# L. Immutability
# ---------------------------------------------------------------------------


def test_summarize_does_not_mutate_input():
    df_in = _standard_two_year_cashflows()
    snapshot = df_in.copy(deep=True)
    summarize_cashflows_by_year(df_in)
    pd.testing.assert_frame_equal(df_in, snapshot)


# ---------------------------------------------------------------------------
# M. Reporting-year dtype robustness
# ---------------------------------------------------------------------------


def test_validate_accepts_numpy_int_reporting_year():
    summary = _valid_summary()
    # Build a copy with reporting_year as an explicit numpy int64 dtype
    summary["reporting_year"] = summary["reporting_year"].astype(np.int64)
    assert validate_annual_cashflow_dataframe(summary) is True


def test_inflection_returns_python_int():
    summary = _valid_summary()
    summary["reporting_year"] = summary["reporting_year"].astype(np.int64)
    result = find_liquidity_inflection_year(summary, use_structural=True)
    assert result == 2027
    assert type(result) is int  # standard Python int, not numpy.int64
