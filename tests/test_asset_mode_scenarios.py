"""Tests for ACTUS asset_mode wiring in Stage-1, Stage-2A, and Stage-2B."""

from pathlib import Path

import pandas as pd

from pk_alm.adapters.aal_asset_portfolio import CSHSpec, PAMSpec, STKSpec
from pk_alm.assets.aal_engine import AALAssetEngineResult
from pk_alm.assets.actus_trajectory import ACTUS_ASSET_TRAJECTORY_COLUMNS
from pk_alm.cashflows.schema import CASHFLOW_COLUMNS
from pk_alm.bvg.mortality import MORTALITY_MODE_EK0105, MORTALITY_MODE_OFF
from pk_alm.scenarios import stage1_baseline as stage1_mod
from pk_alm.scenarios.stage1_baseline import run_stage1_baseline
from pk_alm.scenarios.stage2_baseline import (
    STAGE2_ACTUS_OUTPUT_FILENAMES,
    run_stage2_baseline,
)
from pk_alm.scenarios.stage2b_mortality import (
    STAGE2B_ACTUS_OUTPUT_FILENAMES,
    run_stage2b_mortality,
)


def _fake_specs():
    return (
        PAMSpec("FAKE_PAM", 2026, 2028, 100_000.0, 0.02),
        STKSpec(
            "FAKE_STK",
            2026,
            2028,
            quantity=1_000.0,
            price_at_purchase=100.0,
            price_at_termination=110.0,
            dividend_yield=0.02,
            market_value_growth=0.05,
        ),
        CSHSpec("FAKE_CSH", 2026, 50_000.0),
    )


def _fake_asset_cashflows():
    return pd.DataFrame(
        [
            {
                "contractId": "FAKE_PAM",
                "time": pd.Timestamp("2027-01-01"),
                "type": "IP",
                "payoff": 2_000.0,
                "nominalValue": 100_000.0,
                "currency": "CHF",
                "source": "ACTUS",
            },
            {
                "contractId": "FAKE_PAM",
                "time": pd.Timestamp("2028-12-31"),
                "type": "MD",
                "payoff": 100_000.0,
                "nominalValue": 0.0,
                "currency": "CHF",
                "source": "ACTUS",
            },
            {
                "contractId": "FAKE_STK",
                "time": pd.Timestamp("2028-12-31"),
                "type": "TD",
                "payoff": 110_000.0,
                "nominalValue": 0.0,
                "currency": "CHF",
                "source": "ACTUS",
            },
        ],
        columns=list(CASHFLOW_COLUMNS),
    )


def _patch_fake_asset_engine(monkeypatch) -> None:
    def fake_run_aal_asset_engine(asset_specs=None):
        return AALAssetEngineResult(
            cashflows=_fake_asset_cashflows(),
            contracts=_fake_specs(),
            aal_version="fake",
            notes=("fake phase2 asset engine",),
        )

    monkeypatch.setattr(stage1_mod, "run_aal_asset_engine", fake_run_aal_asset_engine)


def _assert_actus_mode_outputs(result, output_dir: Path, filenames: tuple[str, ...]):
    assert sorted(path.name for path in output_dir.glob("*.csv")) == sorted(filenames)
    assert set(result.cashflows["source"]) == {"ACTUS", "BVG"}
    trajectory_path = output_dir / "actus_asset_trajectory.csv"
    assert trajectory_path.exists()
    trajectory = pd.read_csv(trajectory_path)
    assert list(trajectory.columns) == list(ACTUS_ASSET_TRAJECTORY_COLUMNS)
    assert not result.funding_ratio_trajectory.empty
    assert result.funding_ratio_trajectory["funding_ratio"].notna().all()


def test_stage1_actus_mode_writes_extra_asset_trajectory(tmp_path, monkeypatch):
    _patch_fake_asset_engine(monkeypatch)
    result = run_stage1_baseline(asset_mode="actus", output_dir=tmp_path)

    _assert_actus_mode_outputs(
        result,
        tmp_path,
        (
            "cashflows.csv",
            "valuation_snapshots.csv",
            "annual_cashflows.csv",
            "asset_snapshots.csv",
            "funding_ratio_trajectory.csv",
            "funding_summary.csv",
            "scenario_summary.csv",
            "actus_asset_trajectory.csv",
        ),
    )


def test_stage2a_actus_mode_writes_extra_asset_trajectory(tmp_path, monkeypatch):
    _patch_fake_asset_engine(monkeypatch)
    result = run_stage2_baseline(asset_mode="actus", output_dir=tmp_path)

    _assert_actus_mode_outputs(result, tmp_path, STAGE2_ACTUS_OUTPUT_FILENAMES)


def test_stage2b_actus_mode_writes_extra_asset_trajectory(tmp_path, monkeypatch):
    _patch_fake_asset_engine(monkeypatch)
    result = run_stage2b_mortality(asset_mode="actus", output_dir=tmp_path)

    _assert_actus_mode_outputs(result, tmp_path, STAGE2B_ACTUS_OUTPUT_FILENAMES)


def test_stage2b_actus_mortality_changes_funding_ratio(monkeypatch):
    _patch_fake_asset_engine(monkeypatch)
    mortality_off = run_stage2b_mortality(
        asset_mode="actus",
        mortality_mode=MORTALITY_MODE_OFF,
        output_dir=None,
    )
    mortality_on = run_stage2b_mortality(
        asset_mode="actus",
        mortality_mode=MORTALITY_MODE_EK0105,
        output_dir=None,
    )

    assert not mortality_off.funding_ratio_trajectory["funding_ratio_percent"].equals(
        mortality_on.funding_ratio_trajectory["funding_ratio_percent"]
    )
