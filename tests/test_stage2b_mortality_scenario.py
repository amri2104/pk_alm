from pathlib import Path

import pandas as pd

from pk_alm.bvg.mortality import (
    MORTALITY_MODE_EK0105,
    MORTALITY_MODE_OFF,
)
from pk_alm.scenarios.stage2_baseline import run_stage2_baseline
from pk_alm.scenarios.stage2b_mortality import (
    STAGE2B_OUTPUT_FILENAMES,
    Stage2BMortalityResult,
    run_stage2b_mortality,
)


def test_mortality_off_reproduces_stage2a_outputs_exactly() -> None:
    stage2a = run_stage2_baseline(output_dir=None)
    stage2b = run_stage2b_mortality(mortality_mode=MORTALITY_MODE_OFF, output_dir=None)

    assert isinstance(stage2b, Stage2BMortalityResult)
    assert stage2b.portfolio_states == stage2a.engine_result.portfolio_states
    pd.testing.assert_frame_equal(stage2b.cashflows, stage2a.engine_result.cashflows)
    pd.testing.assert_frame_equal(stage2b.annual_cashflows, stage2a.annual_cashflows)
    pd.testing.assert_frame_equal(stage2b.asset_snapshots, stage2a.asset_snapshots)
    pd.testing.assert_frame_equal(stage2b.funding_summary, stage2a.funding_summary)
    pd.testing.assert_frame_equal(
        stage2b.funding_ratio_trajectory,
        stage2a.funding_ratio_trajectory,
    )


def test_ek0105_does_not_decrement_retired_counts() -> None:
    stage2a = run_stage2_baseline(output_dir=None)
    stage2b = run_stage2b_mortality(
        mortality_mode=MORTALITY_MODE_EK0105,
        output_dir=None,
    )
    assert stage2b.portfolio_states == stage2a.engine_result.portfolio_states
    assert list(
        stage2b.mortality_valuation_snapshots["retired_count_total"]
    ) == [
        state.retired_count_total for state in stage2a.engine_result.portfolio_states
    ]


def test_ek0105_expected_rp_cashflows_are_not_more_negative_than_stage2a() -> None:
    stage2a = run_stage2_baseline(output_dir=None)
    stage2b = run_stage2b_mortality(
        mortality_mode=MORTALITY_MODE_EK0105,
        output_dir=None,
    )
    merged = stage2a.engine_result.cashflows.reset_index().merge(
        stage2b.cashflows.reset_index(),
        on="index",
        suffixes=("_stage2a", "_stage2b"),
    )
    rp = merged[merged["type_stage2a"] == "RP"]
    assert not rp.empty
    assert (rp["payoff_stage2b"].abs() <= rp["payoff_stage2a"].abs() + 1e-9).all()
    assert (rp["payoff_stage2b"].abs() < rp["payoff_stage2a"].abs()).any()


def test_ek0105_mortality_pv_is_not_above_deterministic_pv() -> None:
    result = run_stage2b_mortality(
        mortality_mode=MORTALITY_MODE_EK0105,
        output_dir=None,
    )
    vals = result.mortality_valuation_snapshots
    assert (
        vals["mortality_weighted_retiree_obligation_pv"]
        <= vals["deterministic_retiree_obligation_pv"] + 1e-9
    ).all()


def test_ek0105_does_not_change_non_rp_cashflows_or_add_technical_reserves() -> None:
    stage2a = run_stage2_baseline(output_dir=None)
    stage2b = run_stage2b_mortality(
        mortality_mode=MORTALITY_MODE_EK0105,
        output_dir=None,
    )
    merged = stage2a.engine_result.cashflows.reset_index().merge(
        stage2b.cashflows.reset_index(),
        on="index",
        suffixes=("_stage2a", "_stage2b"),
    )
    non_rp = merged[merged["type_stage2a"] != "RP"]
    assert not non_rp.empty
    assert (
        non_rp[["contractId_stage2a", "time_stage2a", "type_stage2a"]].to_numpy()
        == non_rp[["contractId_stage2b", "time_stage2b", "type_stage2b"]].to_numpy()
    ).all()
    pd.testing.assert_series_equal(
        non_rp["payoff_stage2b"],
        non_rp["payoff_stage2a"],
        check_names=False,
    )
    assert not any(
        "technical_reserve" in column
        for column in stage2b.mortality_valuation_snapshots.columns
    )


def test_ek0105_reuses_stage2a_opening_assets() -> None:
    stage2a = run_stage2_baseline(output_dir=None)
    stage2b = run_stage2b_mortality(
        mortality_mode=MORTALITY_MODE_EK0105,
        output_dir=None,
    )
    assert stage2b.asset_snapshots.iloc[0]["opening_asset_value"] == (
        stage2a.asset_snapshots.iloc[0]["opening_asset_value"]
    )
    assert stage2b.asset_snapshots.iloc[0]["closing_asset_value"] == (
        stage2a.asset_snapshots.iloc[0]["closing_asset_value"]
    )


def test_stage2b_writes_only_stage2b_outputs(tmp_path: Path) -> None:
    out = tmp_path / "stage2b_mortality"
    result = run_stage2b_mortality(output_dir=out)
    assert result.output_dir == out
    assert sorted(p.name for p in out.glob("*.csv")) == sorted(
        STAGE2B_OUTPUT_FILENAMES
    )
    assert not (tmp_path / "stage1_baseline").exists()
    assert not (tmp_path / "stage2a_population").exists()


def test_mortality_assumptions_contains_educational_caveat() -> None:
    result = run_stage2b_mortality(output_dir=None)
    text = result.mortality_assumptions.iloc[0]["source_caveat"]
    assert "educational" in text
    assert "BVG 2020 / VZ 2020" in text
