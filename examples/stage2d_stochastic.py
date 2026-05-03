"""Run the Stage-2D stochastic-rate demonstrator."""

from __future__ import annotations

from pathlib import Path

from pk_alm.scenarios.stage2d_stochastic import run_stage2d_stochastic


def main() -> None:
    result = run_stage2d_stochastic(
        scenario_id="stage2d_stochastic",
        horizon_years=12,
        n_paths=1000,
        seed=42,
        model_active="hull_white",
        model_technical="hull_white",
        output_dir=Path("outputs/stage2d_stochastic"),
    )

    final_row = result.funding_ratio_percentiles.iloc[-1]
    summary = result.funding_ratio_summary.iloc[0]

    print("Stage 2D Stochastic Rates")
    print(f"Final median funding ratio : {final_row['p50']:.2f}%")
    print(f"Final p5/p95 funding ratio : {final_row['p5']:.2f}% / {final_row['p95']:.2f}%")
    print(f"P(underfunding)           : {summary['P_underfunding']:.2%}")
    print("Liquidity inflection distribution:")
    for row in result.liquidity_inflection_distribution.itertuples(index=False):
        label = "none" if row.year == -1 else str(row.year)
        print(f"  {label}: {row.probability:.2%}")
    print(
        "Caveat: active and technical rate paths are independent; real-world "
        "correlation is deferred to a later sprint."
    )
    print("Outputs written to outputs/stage2d_stochastic")


if __name__ == "__main__":
    main()
