"""Dashboard runner wrapper around the canonical Full ALM scenario."""

from __future__ import annotations

from collections.abc import Mapping

from pk_alm.scenarios.full_alm_scenario import (
    FullALMScenarioResult,
    run_full_alm_scenario,
)


SUPPORTED_ASSET_MODES = ("actus",)


def run_dashboard_scenario(params: Mapping[str, object]) -> FullALMScenarioResult:
    """Run the dashboard scenario without writing generated outputs."""
    if not isinstance(params, Mapping):
        raise TypeError(f"params must be a mapping, got {type(params).__name__}")

    asset_mode = str(params.get("asset_mode", "actus"))
    if asset_mode not in SUPPORTED_ASSET_MODES:
        raise ValueError("asset_mode must be 'actus'")

    return run_full_alm_scenario(
        scenario_id=str(params.get("scenario_name", "dashboard_scenario")),
        start_year=int(params.get("start_year", 2026)),
        horizon_years=int(params.get("horizon_years", 12)),
        target_funding_ratio=float(params.get("target_funding_ratio", 1.076)),
        technical_interest_rate=float(
            params.get("technical_discount_rate", 0.0176)
        ),
        active_interest_rate=float(params.get("active_crediting_rate", 0.0176)),
        annual_asset_return=float(params.get("annual_asset_return", 0.0)),
        contribution_multiplier=float(params.get("contribution_multiplier", 1.4)),
        conversion_rate=float(params.get("conversion_rate", 0.068)),
        capital_withdrawal_fraction=float(
            params.get("capital_withdrawal_fraction", 0.35)
        ),
        turnover_rate=float(params.get("turnover_rate", 0.0)),
        salary_growth_rate=float(params.get("salary_growth_rate", 0.0)),
    )

