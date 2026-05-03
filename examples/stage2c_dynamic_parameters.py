"""Run the Stage-2C dynamic-parameter demonstrator."""

from __future__ import annotations

from pathlib import Path

from pk_alm.scenarios.stage2c_dynamic_parameters import run_stage2c_dynamic_parameters


def _linear_path(start: float, end: float, steps: int) -> tuple[float, ...]:
    if steps <= 1:
        return (end,)
    step = (end - start) / (steps - 1)
    return tuple(start + i * step for i in range(steps))


def main() -> None:
    constant = run_stage2c_dynamic_parameters(
        scenario_id="stage2a_equivalent_constants",
        active_interest_rate=0.0176,
        technical_interest_rate=0.0176,
        conversion_rate=0.068,
        output_dir=None,
    )
    dynamic = run_stage2c_dynamic_parameters(
        scenario_id="stage2c_dynamic_parameters",
        active_interest_rate=_linear_path(0.0176, 0.0150, 5),
        technical_interest_rate=_linear_path(0.0176, 0.0150, 5),
        conversion_rate=_linear_path(0.068, 0.060, 8),
        output_dir=Path("outputs/stage2c_dynamic_parameters"),
    )

    constant_initial = float(
        constant.funding_ratio_trajectory.iloc[0]["funding_ratio_percent"]
    )
    constant_final = float(
        constant.funding_ratio_trajectory.iloc[-1]["funding_ratio_percent"]
    )
    dynamic_initial = float(
        dynamic.funding_ratio_trajectory.iloc[0]["funding_ratio_percent"]
    )
    dynamic_final = float(
        dynamic.funding_ratio_trajectory.iloc[-1]["funding_ratio_percent"]
    )

    print("Stage 2C Dynamic Parameters")
    print(f"Constant initial funding ratio : {constant_initial:.2f}%")
    print(f"Constant final funding ratio   : {constant_final:.2f}%")
    print(f"Dynamic initial funding ratio  : {dynamic_initial:.2f}%")
    print(f"Dynamic final funding ratio    : {dynamic_final:.2f}%")
    print(f"Final funding-ratio difference : {dynamic_final - constant_final:.2f} pp")
    print(
        "Caveat: lower UWS reduces pension benefits per CHF capital and can "
        "raise funding ratios, while a lower discount rate raises retiree PV "
        "and can lower funding ratios."
    )
    print("Outputs written to outputs/stage2c_dynamic_parameters")


if __name__ == "__main__":
    main()
