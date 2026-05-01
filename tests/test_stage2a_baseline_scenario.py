import hashlib
from pathlib import Path

import pandas as pd

from pk_alm.bvg.entry_dynamics import EntryAssumptions
from pk_alm.scenarios.stage1_baseline import run_stage1_baseline
from pk_alm.scenarios.stage2_baseline import (
    DEMOGRAPHIC_SUMMARY_COLUMNS,
    STAGE2_OUTPUT_FILENAMES,
    Stage2BaselineResult,
    build_default_initial_portfolio_stage2,
    run_stage2_baseline,
)


def _file_hashes(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    hashes: dict[str, str] = {}
    for file_path in sorted(path.glob("*")):
        if file_path.is_file():
            hashes[file_path.name] = hashlib.sha256(file_path.read_bytes()).hexdigest()
    return hashes


def test_stage2_baseline_runs_end_to_end_without_export() -> None:
    result = run_stage2_baseline(output_dir=None)
    assert isinstance(result, Stage2BaselineResult)
    assert result.output_dir is None
    assert build_default_initial_portfolio_stage2() == result.engine_result.initial_state
    assert list(result.demographic_summary.columns) == list(
        DEMOGRAPHIC_SUMMARY_COLUMNS
    )
    assert list(result.cashflows_by_type.columns) == [
        "reporting_year",
        "type",
        "total_payoff",
    ]


def test_stage2_with_zero_levers_baseline_cashflows_match_stage1() -> None:
    stage1 = run_stage1_baseline(output_dir=None)
    stage2 = run_stage2_baseline(
        salary_growth_rate=0.0,
        turnover_rate=0.0,
        entry_assumptions=EntryAssumptions(entry_count_per_year=0),
        output_dir=None,
    )
    pd.testing.assert_frame_equal(
        stage1.engine_result.cashflows.reset_index(drop=True),
        stage2.engine_result.cashflows.reset_index(drop=True),
        check_dtype=False,
    )
    assert stage1.engine_result.portfolio_states == stage2.engine_result.portfolio_states


def test_stage2_does_not_overwrite_stage1_outputs(tmp_path: Path) -> None:
    protected_dir = Path("outputs/stage1_baseline")
    before_hashes = _file_hashes(protected_dir)
    before = run_stage1_baseline(output_dir=None)
    run_stage2_baseline(output_dir=tmp_path)
    after = run_stage1_baseline(output_dir=None)
    after_hashes = _file_hashes(protected_dir)

    assert after_hashes == before_hashes
    pd.testing.assert_frame_equal(
        before.engine_result.cashflows,
        after.engine_result.cashflows,
    )
    pd.testing.assert_frame_equal(
        before.funding_ratio_trajectory,
        after.funding_ratio_trajectory,
    )


def test_stage2_writes_exactly_nine_csv_outputs_to_requested_dir(tmp_path: Path) -> None:
    output_dir = tmp_path / "stage2a_population"
    result = run_stage2_baseline(output_dir=output_dir)
    assert result.output_dir == output_dir
    assert sorted(p.name for p in output_dir.glob("*.csv")) == sorted(
        STAGE2_OUTPUT_FILENAMES
    )
    for filename in STAGE2_OUTPUT_FILENAMES:
        df = pd.read_csv(output_dir / filename)
        assert isinstance(df, pd.DataFrame)


def test_demographic_summary_counts_persons_and_expected_columns() -> None:
    result = run_stage2_baseline(
        horizon_years=1,
        salary_growth_rate=0.0,
        turnover_rate=0.2,
        entry_assumptions=EntryAssumptions(entry_count_per_year=2),
        output_dir=None,
    )
    summary = result.demographic_summary
    assert list(summary.columns) == list(DEMOGRAPHIC_SUMMARY_COLUMNS)
    row = summary.iloc[0]
    assert int(row["entries"]) == 2
    assert int(row["exits"]) == 2
    assert int(row["retirements"]) == 0
    assert int(row["active_count_end"]) == result.engine_result.final_state.active_count_total
    assert int(row["retired_count_end"]) == result.engine_result.final_state.retired_count_total
