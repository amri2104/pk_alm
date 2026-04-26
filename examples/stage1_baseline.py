"""Manual-run script for the Stage-1 baseline scenario.

Importing this module is a no-op. The scenario only runs when this file is
executed directly (`python examples/stage1_baseline.py`).
"""

from pathlib import Path

from pk_alm.scenarios.stage1_baseline import run_stage1_baseline


if __name__ == "__main__":
    result = run_stage1_baseline(output_dir=Path("outputs/stage1_baseline"))

    print("=== Stage-1 Baseline Scenario ===")
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
        f"{result.funding_ratio_trajectory.iloc[-1]['funding_ratio_percent']:.2f}"
    )
    print(
        f"Inflection year (struct) : "
        f"{result.liquidity_inflection_year_structural}"
    )
    print(f"Inflection year (net)    : {result.liquidity_inflection_year_net}")
    print("Output files:")
    for key, path in result.output_paths.items():
        print(f"  {key:25s} -> {path}")
