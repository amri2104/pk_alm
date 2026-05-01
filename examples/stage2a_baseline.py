from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pk_alm.scenarios.stage1_baseline import run_stage1_baseline
from pk_alm.scenarios.stage2_baseline import run_stage2_baseline


def main() -> None:
    stage1 = run_stage1_baseline(output_dir=None)
    stage2 = run_stage2_baseline(output_dir=Path("outputs/stage2a_population"))

    print("Stage 2A demographic summary")
    print(
        stage2.demographic_summary[
            ["projection_year", "entries", "exits", "retirements"]
        ].to_string(index=False)
    )
    print()
    print(
        "Caveat: The default Stage-2A demo uses a small population. With "
        "turnover_rate=0.02 and deterministic floor(count * turnover_rate), "
        "no exits are realised in the default run. The default Stage-2A "
        "result is therefore mainly driven by annual new entrants and salary "
        "growth. Turnover functionality is implemented and tested separately, "
        "but it is not a material driver of the default demo output."
    )

    stage1_final = stage1.funding_ratio_trajectory.iloc[-1][
        "funding_ratio_percent"
    ]
    stage2_final = stage2.funding_ratio_trajectory.iloc[-1][
        "funding_ratio_percent"
    ]
    print()
    print(f"Stage-1 final funding ratio: {stage1_final:.2f}%")
    print(f"Stage-2A final funding ratio: {stage2_final:.2f}%")
    print("Outputs written to outputs/stage2a_population")


if __name__ == "__main__":
    main()
