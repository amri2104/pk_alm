from __future__ import annotations

from pk_alm import run_stage1_stress_scenarios


def main() -> None:
    try:
        results = run_stage1_stress_scenarios()
    except Exception as exc:
        raise SystemExit(
            "Stage 1 requires awesome_actus_lib and a reachable ACTUS service for asset cashflows. "
            f"Original error: {exc}"
        ) from exc

    for scenario_name, result in results.items():
        row0 = result.kpis.loc[result.kpis["year"] == 0].iloc[0]
        print(
            f"{scenario_name}: "
            f"DG={row0['funding_ratio']:.2f}%, "
            f"income_yield={row0['income_yield']:.2%}, "
            f"annual_inflection={row0['annual_net_cf_inflection_year']}, "
            f"cumulative_depletion={row0['cumulative_net_cf_depletion_year']}"
        )


if __name__ == "__main__":
    main()
