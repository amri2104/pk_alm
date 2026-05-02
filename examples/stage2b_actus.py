"""Run Stage 2B mortality with the live AAL/ACTUS asset mode."""

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pk_alm.scenarios.stage2b_mortality import run_stage2b_mortality


def _first_below_100(result) -> str:
    below = result.funding_ratio_trajectory[
        result.funding_ratio_trajectory["funding_ratio_percent"] < 100.0
    ]
    if below.empty:
        return "none"
    return str(int(below.iloc[0]["projection_year"]))


def _print_source_breakdown(result) -> None:
    summary = (
        result.cashflows.groupby("source", as_index=False)["payoff"]
        .agg(rows="count", total_payoff="sum")
        .sort_values("source")
    )
    print("Source breakdown:")
    print(summary.to_string(index=False))


def main() -> None:
    result = run_stage2b_mortality(
        asset_mode="actus",
        output_dir=Path("outputs/stage2b_actus"),
    )
    print("=== Stage-2B ACTUS Asset Mode ===")
    print(f"Mortality mode          : {result.mortality_mode}")
    print(f"Mortality table         : {result.mortality_table_id}")
    print(
        "Opening funding ratio % : "
        f"{result.funding_ratio_trajectory.iloc[0]['funding_ratio_percent']:.2f}"
    )
    print(
        "Final funding ratio %   : "
        f"{result.funding_ratio_trajectory.iloc[-1]['funding_ratio_percent']:.2f}"
    )
    print(f"First year below 100%   : {_first_below_100(result)}")
    print(
        "Final asset trajectory  : "
        f"{result.actus_asset_trajectory.iloc[-1]['closing_asset_value']:.2f}"
    )
    _print_source_breakdown(result)
    print("Outputs written to outputs/stage2b_actus")


if __name__ == "__main__":
    main()
