import math

import pandas as pd
import pytest

from pk_alm.analytics.monthly_reconciliation import (
    MONTHLY_RECONCILIATION_COLUMNS,
    MonthlyReconciliationRow,
    build_monthly_bvg_reconciliation_for_state,
    reconcile_monthly_bvg_cashflows_to_annual,
    validate_monthly_reconciliation_dataframe,
)
from pk_alm.bvg.cashflow_generation import (
    generate_bvg_cashflow_dataframe_for_state,
)
from pk_alm.bvg.cohorts import ActiveCohort, RetiredCohort
from pk_alm.bvg.monthly_cashflow_generation import (
    generate_monthly_bvg_cashflow_dataframe_for_state,
)
from pk_alm.bvg.portfolio import BVGPortfolioState
from pk_alm.cashflows.schema import CASHFLOW_COLUMNS, CashflowRecord
from pk_alm.scenarios.stage1_baseline import run_stage1_baseline

REPORTING_YEAR = 2026


# ---------------------------------------------------------------------------
# Shared cohorts and portfolio
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
# Helpers
# ---------------------------------------------------------------------------


def _empty_cashflow_dataframe() -> pd.DataFrame:
    return pd.DataFrame(columns=list(CASHFLOW_COLUMNS))


def _ka_record() -> CashflowRecord:
    return CashflowRecord(
        contractId="ACT_55",
        time=pd.Timestamp(f"{REPORTING_YEAR}-12-31"),
        type="KA",
        payoff=-50_000.0,
        nominalValue=0.0,
        currency="CHF",
        source="BVG",
    )


# ---------------------------------------------------------------------------
# A. Standard reconciliation
# ---------------------------------------------------------------------------


def test_standard_reconciliation_returns_two_rows():
    annual_df = generate_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, f"{REPORTING_YEAR}-12-31", contribution_multiplier=1.4
    )
    monthly_df = generate_monthly_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, REPORTING_YEAR, contribution_multiplier=1.4
    )
    result = reconcile_monthly_bvg_cashflows_to_annual(
        annual_df, monthly_df, REPORTING_YEAR
    )
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 2


def test_standard_reconciliation_columns_are_canonical():
    annual_df = generate_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, f"{REPORTING_YEAR}-12-31"
    )
    monthly_df = generate_monthly_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, REPORTING_YEAR
    )
    result = reconcile_monthly_bvg_cashflows_to_annual(
        annual_df, monthly_df, REPORTING_YEAR
    )
    assert list(result.columns) == list(MONTHLY_RECONCILIATION_COLUMNS)


def test_standard_reconciliation_rows_are_pr_then_rp():
    annual_df = generate_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, f"{REPORTING_YEAR}-12-31"
    )
    monthly_df = generate_monthly_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, REPORTING_YEAR
    )
    result = reconcile_monthly_bvg_cashflows_to_annual(
        annual_df, monthly_df, REPORTING_YEAR
    )
    assert list(result["type"]) == ["PR", "RP"]


def test_standard_reconciliation_is_close_for_both_types():
    annual_df = generate_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, f"{REPORTING_YEAR}-12-31", contribution_multiplier=1.4
    )
    monthly_df = generate_monthly_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, REPORTING_YEAR, contribution_multiplier=1.4
    )
    result = reconcile_monthly_bvg_cashflows_to_annual(
        annual_df, monthly_df, REPORTING_YEAR
    )
    assert result["is_close"].all()
    assert (result["abs_difference"] < 1e-9).all()


# ---------------------------------------------------------------------------
# B. Convenience builder
# ---------------------------------------------------------------------------


def test_convenience_builder_validates_and_matches_pieces():
    direct = build_monthly_bvg_reconciliation_for_state(
        PORTFOLIO, REPORTING_YEAR, contribution_multiplier=1.4
    )
    assert validate_monthly_reconciliation_dataframe(direct) is True
    assert list(direct["type"]) == ["PR", "RP"]
    assert direct["is_close"].all()


def test_convenience_builder_rejects_invalid_portfolio():
    with pytest.raises(TypeError):
        build_monthly_bvg_reconciliation_for_state(None, REPORTING_YEAR)


def test_convenience_builder_rejects_invalid_year():
    with pytest.raises(ValueError):
        build_monthly_bvg_reconciliation_for_state(PORTFOLIO, -1)


# ---------------------------------------------------------------------------
# C. Tampered monthly cashflow
# ---------------------------------------------------------------------------


def test_tampered_monthly_pr_marks_pr_row_not_close():
    annual_df = generate_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, f"{REPORTING_YEAR}-12-31"
    )
    monthly_df = generate_monthly_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, REPORTING_YEAR
    )
    tampered = monthly_df.copy()
    pr_indices = tampered.index[tampered["type"] == "PR"]
    tampered.loc[pr_indices[0], "payoff"] = (
        tampered.loc[pr_indices[0], "payoff"] + 1.0
    )

    result = reconcile_monthly_bvg_cashflows_to_annual(
        annual_df, tampered, REPORTING_YEAR
    )
    pr_row = result.loc[result["type"] == "PR"].iloc[0]
    rp_row = result.loc[result["type"] == "RP"].iloc[0]

    assert bool(pr_row["is_close"]) is False
    assert pr_row["abs_difference"] > 0
    assert bool(rp_row["is_close"]) is True


# ---------------------------------------------------------------------------
# D. Empty inputs
# ---------------------------------------------------------------------------


def test_empty_inputs_produce_zero_pr_rp_rows():
    annual_df = _empty_cashflow_dataframe()
    monthly_df = _empty_cashflow_dataframe()
    result = reconcile_monthly_bvg_cashflows_to_annual(
        annual_df, monthly_df, REPORTING_YEAR
    )
    assert list(result["type"]) == ["PR", "RP"]
    assert (result["annual_payoff"] == 0.0).all()
    assert (result["monthly_payoff"] == 0.0).all()
    assert (result["difference"] == 0.0).all()
    assert (result["abs_difference"] == 0.0).all()
    assert result["is_close"].all()


# ---------------------------------------------------------------------------
# E. KA ignored
# ---------------------------------------------------------------------------


def test_ka_in_annual_is_ignored_and_does_not_appear_in_output():
    base_annual = generate_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, f"{REPORTING_YEAR}-12-31"
    )
    ka_row_df = pd.DataFrame([_ka_record().to_dict()], columns=list(CASHFLOW_COLUMNS))
    annual_with_ka = pd.concat([base_annual, ka_row_df], ignore_index=True)
    monthly_df = generate_monthly_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, REPORTING_YEAR
    )

    result = reconcile_monthly_bvg_cashflows_to_annual(
        annual_with_ka, monthly_df, REPORTING_YEAR
    )
    assert list(result["type"]) == ["PR", "RP"]
    assert result["is_close"].all()


def test_ka_in_monthly_is_ignored_and_does_not_appear_in_output():
    annual_df = generate_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, f"{REPORTING_YEAR}-12-31"
    )
    base_monthly = generate_monthly_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, REPORTING_YEAR
    )
    ka_row_df = pd.DataFrame([_ka_record().to_dict()], columns=list(CASHFLOW_COLUMNS))
    monthly_with_ka = pd.concat([base_monthly, ka_row_df], ignore_index=True)

    result = reconcile_monthly_bvg_cashflows_to_annual(
        annual_df, monthly_with_ka, REPORTING_YEAR
    )
    assert list(result["type"]) == ["PR", "RP"]
    assert result["is_close"].all()


# ---------------------------------------------------------------------------
# F. Validation failures
# ---------------------------------------------------------------------------


def test_reconcile_rejects_non_dataframe_annual():
    monthly_df = generate_monthly_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, REPORTING_YEAR
    )
    with pytest.raises(TypeError):
        reconcile_monthly_bvg_cashflows_to_annual(
            "not a dataframe", monthly_df, REPORTING_YEAR
        )


def test_reconcile_rejects_non_dataframe_monthly():
    annual_df = generate_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, f"{REPORTING_YEAR}-12-31"
    )
    with pytest.raises(TypeError):
        reconcile_monthly_bvg_cashflows_to_annual(
            annual_df, "not a dataframe", REPORTING_YEAR
        )


def test_reconcile_rejects_bool_reporting_year():
    annual_df = generate_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, f"{REPORTING_YEAR}-12-31"
    )
    monthly_df = generate_monthly_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, REPORTING_YEAR
    )
    with pytest.raises(TypeError):
        reconcile_monthly_bvg_cashflows_to_annual(
            annual_df, monthly_df, True
        )


def test_validator_rejects_non_dataframe():
    with pytest.raises(TypeError):
        validate_monthly_reconciliation_dataframe("not a dataframe")


def test_validator_rejects_missing_column():
    df = pd.DataFrame(
        {
            "reporting_year": [2026],
            "type": ["PR"],
            "annual_payoff": [10.0],
            "monthly_payoff": [10.0],
            "difference": [0.0],
            "abs_difference": [0.0],
            # is_close missing
        }
    )
    with pytest.raises(ValueError):
        validate_monthly_reconciliation_dataframe(df)


def test_validator_rejects_wrong_column_order():
    rows = [
        {column: 0 for column in MONTHLY_RECONCILIATION_COLUMNS}
    ]
    rows[0]["reporting_year"] = 2026
    rows[0]["type"] = "PR"
    rows[0]["annual_payoff"] = 0.0
    rows[0]["monthly_payoff"] = 0.0
    rows[0]["difference"] = 0.0
    rows[0]["abs_difference"] = 0.0
    rows[0]["is_close"] = True
    columns = list(MONTHLY_RECONCILIATION_COLUMNS)
    columns[0], columns[1] = columns[1], columns[0]
    df = pd.DataFrame(rows, columns=columns)
    with pytest.raises(ValueError):
        validate_monthly_reconciliation_dataframe(df)


def test_validator_rejects_missing_value():
    df = pd.DataFrame(
        [
            {
                "reporting_year": 2026,
                "type": "PR",
                "annual_payoff": float("nan"),
                "monthly_payoff": 0.0,
                "difference": 0.0,
                "abs_difference": 0.0,
                "is_close": True,
            }
        ],
        columns=list(MONTHLY_RECONCILIATION_COLUMNS),
    )
    with pytest.raises(ValueError):
        validate_monthly_reconciliation_dataframe(df)


def test_validator_rejects_duplicate_year_type_pair():
    row = {
        "reporting_year": 2026,
        "type": "PR",
        "annual_payoff": 0.0,
        "monthly_payoff": 0.0,
        "difference": 0.0,
        "abs_difference": 0.0,
        "is_close": True,
    }
    df = pd.DataFrame([row, row], columns=list(MONTHLY_RECONCILIATION_COLUMNS))
    with pytest.raises(ValueError):
        validate_monthly_reconciliation_dataframe(df)


def test_validator_rejects_invalid_event_type():
    df = pd.DataFrame(
        [
            {
                "reporting_year": 2026,
                "type": "KA",
                "annual_payoff": 0.0,
                "monthly_payoff": 0.0,
                "difference": 0.0,
                "abs_difference": 0.0,
                "is_close": True,
            }
        ],
        columns=list(MONTHLY_RECONCILIATION_COLUMNS),
    )
    with pytest.raises(ValueError):
        validate_monthly_reconciliation_dataframe(df)


def test_validator_rejects_inconsistent_difference_identity():
    df = pd.DataFrame(
        [
            {
                "reporting_year": 2026,
                "type": "PR",
                "annual_payoff": 100.0,
                "monthly_payoff": 100.0,
                "difference": 5.0,  # should be 0.0
                "abs_difference": 5.0,
                "is_close": True,
            }
        ],
        columns=list(MONTHLY_RECONCILIATION_COLUMNS),
    )
    with pytest.raises(ValueError):
        validate_monthly_reconciliation_dataframe(df)


def test_validator_rejects_inconsistent_abs_difference_identity():
    df = pd.DataFrame(
        [
            {
                "reporting_year": 2026,
                "type": "PR",
                "annual_payoff": 100.0,
                "monthly_payoff": 105.0,
                "difference": 5.0,
                "abs_difference": 99.0,  # should be 5.0
                "is_close": False,
            }
        ],
        columns=list(MONTHLY_RECONCILIATION_COLUMNS),
    )
    with pytest.raises(ValueError):
        validate_monthly_reconciliation_dataframe(df)


def test_validator_rejects_inconsistent_is_close_identity():
    df = pd.DataFrame(
        [
            {
                "reporting_year": 2026,
                "type": "PR",
                "annual_payoff": 100.0,
                "monthly_payoff": 200.0,
                "difference": 100.0,
                "abs_difference": 100.0,
                "is_close": True,  # should be False
            }
        ],
        columns=list(MONTHLY_RECONCILIATION_COLUMNS),
    )
    with pytest.raises(ValueError):
        validate_monthly_reconciliation_dataframe(df)


def test_dataclass_rejects_bool_reporting_year():
    with pytest.raises(TypeError):
        MonthlyReconciliationRow(
            reporting_year=True,
            type="PR",
            annual_payoff=0.0,
            monthly_payoff=0.0,
            difference=0.0,
            abs_difference=0.0,
            is_close=True,
        )


# ---------------------------------------------------------------------------
# G. No Stage-1 side effects
# ---------------------------------------------------------------------------


def test_reconciliation_does_not_change_stage1_baseline_outputs():
    before = run_stage1_baseline(output_dir=None)

    # Run reconciliation work between the two baseline calls.
    build_monthly_bvg_reconciliation_for_state(
        PORTFOLIO, REPORTING_YEAR, contribution_multiplier=1.4
    )
    annual_df = generate_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, f"{REPORTING_YEAR}-12-31"
    )
    monthly_df = generate_monthly_bvg_cashflow_dataframe_for_state(
        PORTFOLIO, REPORTING_YEAR
    )
    reconcile_monthly_bvg_cashflows_to_annual(
        annual_df, monthly_df, REPORTING_YEAR
    )

    after = run_stage1_baseline(output_dir=None)

    pd.testing.assert_frame_equal(
        before.engine_result.cashflows,
        after.engine_result.cashflows,
    )
    pd.testing.assert_frame_equal(
        before.annual_cashflows,
        after.annual_cashflows,
    )
    pd.testing.assert_frame_equal(
        before.funding_ratio_trajectory,
        after.funding_ratio_trajectory,
    )


# ---------------------------------------------------------------------------
# Identity sanity check on the dataclass
# ---------------------------------------------------------------------------


def test_dataclass_identity_passes_for_consistent_inputs():
    row = MonthlyReconciliationRow(
        reporting_year=2026,
        type="RP",
        annual_payoff=-150_000.0,
        monthly_payoff=-150_000.0,
        difference=0.0,
        abs_difference=0.0,
        is_close=True,
    )
    assert row.is_close is True
    assert math.isclose(row.difference, 0.0, abs_tol=1e-9)
