"""Manual-run script for the Stage-1 baseline scenario.

Importing this module is a no-op. The scenario only runs when this file is
executed directly (`python examples/stage1_baseline.py`).
"""

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pk_alm.scenarios.stage1_baseline import run_stage1_baseline


if __name__ == "__main__":
    result = run_stage1_baseline(output_dir=Path("outputs/stage1_baseline"))
    scenario = result.scenario_summary.iloc[0]

    print("=== Stage-1 Baseline Scenario ===")
    print(f"Scenario ID              : {scenario['scenario_id']}")
    print(f"Portfolio states         : {len(result.engine_result.portfolio_states)}")
    print(f"Cashflow rows            : {len(result.engine_result.cashflows)}")
    print(f"Annual cashflow rows     : {len(result.annual_cashflows)}")
    print(f"Asset snapshot rows      : {len(result.asset_snapshots)}")
    print(f"Funding-ratio rows       : {len(result.funding_ratio_trajectory)}")
    print(
        f"Initial funding ratio %  : "
        f"{result.funding_ratio_trajectory.iloc[0]['funding_ratio_percent']:.2f}"
    )
    print(
        f"Final funding ratio %    : "
        f"{scenario['final_funding_ratio_percent']:.2f}"
    )
    print(
        f"Minimum funding ratio %  : "
        f"{scenario['minimum_funding_ratio_percent']:.2f}"
    )
    print(
        f"Min FR projection year   : "
        f"{int(scenario['minimum_funding_ratio_projection_year'])}"
    )
    print(
        f"Years below 100%         : "
        f"{int(scenario['years_below_100_percent'])}"
    )
    print(
        f"Years below target       : "
        f"{int(scenario['years_below_target_percent'])}"
    )
    print(f"Final underfunded        : {scenario['final_underfunded']}")
    print(
        f"Inflection year (struct) : "
        f"{scenario['liquidity_inflection_year_structural']}"
    )
    print(
        f"Inflection year (net)    : "
        f"{scenario['liquidity_inflection_year_net']}"
    )
    print("Output files:")
    for key, path in result.output_paths.items():
        print(f"  {key:25s} -> {path}")
