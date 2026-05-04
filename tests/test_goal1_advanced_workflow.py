"""Smoke tests for the Goal-1 advanced ALM workflow."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from pk_alm.workflows.goal1_advanced_workflow import (
    DEFAULT_ACTIVE_TABLE,
    DEFAULT_ALLOCATION_TABLE,
    DEFAULT_BOND_TABLE,
    DEFAULT_RETIREE_TABLE,
    GOAL1_ADVANCED_OUTPUT_DIR,
    PROTECTED_OUTPUT_DIRS,
    STAGE_COMPARISON_OUTPUT_DIR,
    Goal1AdvancedInput,
    asset_table_to_specs,
    population_tables_to_portfolio_state,
    run_goal1_advanced_alm,
    suggest_mortality_table_from_gender,
)
from pk_alm.workflows.stage_app_workflow import PROTECTED_OUTPUT_DIRS as STAGE_PROTECTED


def _minimal_input(tmp_path: Path, **overrides: object) -> Goal1AdvancedInput:
    base = {
        "allocation_table": DEFAULT_ALLOCATION_TABLE,
        "bond_table": DEFAULT_BOND_TABLE,
        "active_table": DEFAULT_ACTIVE_TABLE,
        "retiree_table": DEFAULT_RETIREE_TABLE,
        "horizon_years": 1,
        "asset_engine_mode": "deterministic_proxy",
        "output_dir": tmp_path / "goal1_test_out",
    }
    base.update(overrides)
    return Goal1AdvancedInput(**base)  # type: ignore[arg-type]


def test_goal1_advanced_output_dir_not_protected() -> None:
    for protected in STAGE_PROTECTED:
        assert GOAL1_ADVANCED_OUTPUT_DIR != protected
        resolved = GOAL1_ADVANCED_OUTPUT_DIR.resolve(strict=False)
        try:
            resolved.relative_to(protected.resolve(strict=False))
            pytest.fail(f"{GOAL1_ADVANCED_OUTPUT_DIR} is inside protected {protected}")
        except ValueError:
            pass


def test_rejects_protected_output_dir() -> None:
    with pytest.raises(ValueError, match="must not target"):
        run_goal1_advanced_alm(
            Goal1AdvancedInput(
                allocation_table=DEFAULT_ALLOCATION_TABLE,
                bond_table=DEFAULT_BOND_TABLE,
                active_table=DEFAULT_ACTIVE_TABLE,
                retiree_table=DEFAULT_RETIREE_TABLE,
                output_dir=Path("outputs/stage1_baseline"),
                asset_engine_mode="deterministic_proxy",
            )
        )


def test_population_tables_to_portfolio_state() -> None:
    state = population_tables_to_portfolio_state(DEFAULT_ACTIVE_TABLE, DEFAULT_RETIREE_TABLE)
    assert state.member_count_total > 0
    assert len(state.active_cohorts) == len(DEFAULT_ACTIVE_TABLE)
    assert len(state.retired_cohorts) == len(DEFAULT_RETIREE_TABLE)


def test_asset_table_to_specs_default() -> None:
    specs = asset_table_to_specs(
        DEFAULT_ALLOCATION_TABLE,
        DEFAULT_BOND_TABLE,
        start_year=2026,
        target_assets=10_000_000.0,
    )
    assert len(specs) > 0


def test_suggest_mortality_table_from_gender_female() -> None:
    table_id = suggest_mortality_table_from_gender(DEFAULT_RETIREE_TABLE)
    assert isinstance(table_id, str)
    assert table_id


def test_run_goal1_advanced_alm_deterministic_proxy(tmp_path: Path) -> None:
    inp = _minimal_input(tmp_path)
    result = run_goal1_advanced_alm(inp)

    assert result.output_dir.exists()
    assert not result.cashflows.empty
    assert not result.funding_ratio_trajectory.empty
    assert not result.kpi_summary.empty
    assert not result.validation_checks.empty
    assert result.stochastic_summary is None
    assert result.output_paths
    assert result.plot_paths


def test_result_kpi_columns(tmp_path: Path) -> None:
    result = run_goal1_advanced_alm(_minimal_input(tmp_path))
    row = result.kpi_summary.iloc[0]
    assert "current_funding_ratio_percent" in row.index
    assert "final_funding_ratio_percent" in row.index
    assert "income_yield" in row.index


def test_output_csvs_written(tmp_path: Path) -> None:
    result = run_goal1_advanced_alm(_minimal_input(tmp_path))
    for key, path in result.output_paths.items():
        assert path.exists(), f"output CSV missing: {key} at {path}"


def test_validation_checks_pass_for_defaults(tmp_path: Path) -> None:
    result = run_goal1_advanced_alm(_minimal_input(tmp_path))
    df = result.validation_checks
    metrics = list(df["metric"].astype(str))
    alloc_metric = next(m for m in metrics if "Allocation weights" in m)
    alloc_row = df[df["metric"] == alloc_metric].iloc[0]
    assert bool(alloc_row["passed"])


@pytest.mark.parametrize(
    "preset",
    ("Interest +100bp", "Interest -100bp", "Equity -20%", "Real Estate -15%", "Combined"),
)
def test_scenario_presets_run_without_error(preset: str, tmp_path: Path) -> None:
    inp = _minimal_input(tmp_path, scenario_preset=preset, output_dir=tmp_path / preset)
    result = run_goal1_advanced_alm(inp)
    assert not result.funding_ratio_trajectory.empty


def test_assumption_income_cashflows_emitted_per_yield_year() -> None:
    from pk_alm.actus_asset_engine.aal_asset_portfolio import STKSpec
    from pk_alm.workflows.goal1_advanced_workflow import (
        _build_assumption_income_cashflows,
    )

    spec = STKSpec(
        contract_id="TEST_EQ",
        start_year=2026,
        divestment_year=2031,
        quantity=100.0,
        price_at_purchase=100.0,
        price_at_termination=140.0,
        currency="CHF",
        dividend_yield=0.025,
        market_value_growth=0.04,
    )
    df = _build_assumption_income_cashflows(
        (spec,), horizon_years=5, start_year=2026
    )
    assert len(df) == 5
    assert (df["type"] == "IP").all()
    assert (df["source"] == "MANUAL").all()
    assert df["payoff"].iloc[0] == pytest.approx(100.0 * 100.0 * 0.025)


def test_assumption_income_cashflows_skips_zero_yield_specs() -> None:
    from pk_alm.actus_asset_engine.aal_asset_portfolio import STKSpec
    from pk_alm.workflows.goal1_advanced_workflow import (
        _build_assumption_income_cashflows,
    )

    spec = STKSpec(
        contract_id="TEST_ALT",
        start_year=2026,
        divestment_year=2030,
        quantity=10.0,
        price_at_purchase=100.0,
        price_at_termination=110.0,
        currency="CHF",
        dividend_yield=0.0,
        market_value_growth=0.03,
    )
    df = _build_assumption_income_cashflows(
        (spec,), horizon_years=4, start_year=2026
    )
    assert df.empty
