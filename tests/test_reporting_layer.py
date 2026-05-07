"""Smoke tests for the BVG reporting layer."""

from __future__ import annotations

import pandas as pd

from pk_alm.bvg_liability_engine.assumptions import (
    BVGAssumptions,
    EntryAssumptions,
    FlatRateCurve,
    MortalityAssumptions,
    StepRateCurve,
)
from pk_alm.bvg_liability_engine.domain_models.cohorts import (
    ActiveCohort,
    RetiredCohort,
)
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.bvg_liability_engine.orchestration.generic_engine import run_bvg_engine
from pk_alm.bvg_liability_engine.population_dynamics.entry_policies import (
    FixedEntryPolicy,
    NoEntryPolicy,
)
from pk_alm.bvg_liability_engine.reporting import (
    build_assumption_report,
    build_summary_trajectory,
    build_validation_report,
)


def _initial() -> BVGPortfolioState:
    return BVGPortfolioState(
        active_cohorts=(
            ActiveCohort(
                cohort_id="ACT_40",
                age=40,
                count=10,
                gross_salary_per_person=85_000.0,
                capital_active_per_person=120_000.0,
            ),
        ),
        retired_cohorts=(
            RetiredCohort(
                cohort_id="RET_70",
                age=70,
                count=5,
                annual_pension_per_person=30_000.0,
                capital_rente_per_person=450_000.0,
            ),
        ),
    )


def _assumptions() -> BVGAssumptions:
    return BVGAssumptions(
        start_year=2026,
        horizon_years=4,
        retirement_age=65,
        valuation_terminal_age=90,
        active_crediting_rate=StepRateCurve({2026: 0.0125, 2028: 0.0150}),
        retired_interest_rate=FlatRateCurve(0.0176),
        technical_discount_rate=FlatRateCurve(0.0176),
        economic_discount_rate=FlatRateCurve(0.0100),
        salary_growth_rate=FlatRateCurve(0.015),
        conversion_rate=FlatRateCurve(0.068),
        turnover_rate=0.02,
        capital_withdrawal_fraction=0.35,
        contribution_multiplier=1.4,
        mortality=MortalityAssumptions(mode="off"),
        entry_policy=FixedEntryPolicy(EntryAssumptions(entry_count_per_year=1)),
    )


def test_build_assumption_report_returns_table_with_all_keys() -> None:
    df = build_assumption_report(_assumptions())
    assert list(df.columns) == ["parameter", "value", "unit", "description"]
    keys = set(df["parameter"])
    assert {"start_year", "horizon_years", "active_crediting_rate", "mortality.mode", "entry_policy"} <= keys
    # Step curve summarized as 'step ...'
    active_row = df.loc[df["parameter"] == "active_crediting_rate", "value"].iloc[0]
    assert active_row.startswith("step ")


def test_build_summary_trajectory_one_row_per_state() -> None:
    result = run_bvg_engine(initial_state=_initial(), assumptions=_assumptions())
    df = build_summary_trajectory(result)
    assert len(df) == len(result.portfolio_states)
    assert {"annual_PR", "annual_RP", "annual_KA", "net_bvg_cashflow"} <= set(df.columns)
    # Year 0 has no cashflows
    assert df.iloc[0]["annual_PR"] == 0.0
    # Subsequent years should have non-zero PR
    assert df.iloc[1]["annual_PR"] > 0.0


def test_build_validation_report_all_ok_for_clean_run() -> None:
    result = run_bvg_engine(initial_state=_initial(), assumptions=_assumptions())
    report = build_validation_report(result)
    assert list(report.columns) == [
        "check_name",
        "status",
        "observed",
        "expected",
        "notes",
    ]
    failures = report[report["status"] == "fail"]
    assert failures.empty, f"unexpected failures: {failures}"


def test_build_validation_report_includes_ex_check() -> None:
    a = BVGAssumptions(
        start_year=2026,
        horizon_years=2,
        retirement_age=65,
        valuation_terminal_age=90,
        active_crediting_rate=FlatRateCurve(0.0125),
        retired_interest_rate=FlatRateCurve(0.0176),
        technical_discount_rate=FlatRateCurve(0.0176),
        economic_discount_rate=FlatRateCurve(0.0100),
        salary_growth_rate=FlatRateCurve(0.0),
        conversion_rate=FlatRateCurve(0.068),
        turnover_rate=0.0,
        capital_withdrawal_fraction=0.35,
        contribution_multiplier=1.0,
        mortality=MortalityAssumptions(mode="off"),
        entry_policy=NoEntryPolicy(),
    )
    result = run_bvg_engine(initial_state=_initial(), assumptions=a)
    report = build_validation_report(result)
    ex_row = report[report["check_name"] == "ex_payoffs_non_positive_sum"].iloc[0]
    assert ex_row["status"] == "ok"
