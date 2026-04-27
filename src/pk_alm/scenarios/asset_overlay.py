"""Asset cashflow overlay scenario for the shared cashflow schema.

This module combines the deterministic BVG baseline cashflows with
ACTUS-style asset fixture cashflows in a separate helper. It does not import
or call AAL, does not modify the default Stage-1 baseline, and is a
demonstration of the shared cashflow schema rather than a full asset engine.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from pk_alm.adapters.actus_fixtures import (
    build_fixed_rate_bond_cashflow_dataframe,
)
from pk_alm.analytics.cashflows import (
    find_liquidity_inflection_year,
    summarize_cashflows_by_year,
    validate_annual_cashflow_dataframe,
)
from pk_alm.cashflows.schema import validate_cashflow_dataframe
from pk_alm.scenarios.stage1_baseline import (
    Stage1BaselineResult,
    run_stage1_baseline,
)


@dataclass(frozen=True)
class AssetOverlayResult:
    """Result container for one BVG + ACTUS-style asset cashflow overlay."""

    baseline_result: Stage1BaselineResult
    asset_cashflows: pd.DataFrame
    combined_cashflows: pd.DataFrame
    combined_annual_cashflows: pd.DataFrame
    combined_liquidity_inflection_year_structural: int | None
    combined_liquidity_inflection_year_net: int | None

    def __post_init__(self) -> None:
        if not isinstance(self.baseline_result, Stage1BaselineResult):
            raise TypeError(
                f"baseline_result must be Stage1BaselineResult, "
                f"got {type(self.baseline_result).__name__}"
            )

        if not isinstance(self.asset_cashflows, pd.DataFrame):
            raise TypeError(
                f"asset_cashflows must be a pandas DataFrame, "
                f"got {type(self.asset_cashflows).__name__}"
            )
        validate_cashflow_dataframe(self.asset_cashflows)
        if not (self.asset_cashflows["source"] == "ACTUS").all():
            raise ValueError('asset_cashflows source values must all be "ACTUS"')

        if not isinstance(self.combined_cashflows, pd.DataFrame):
            raise TypeError(
                f"combined_cashflows must be a pandas DataFrame, "
                f"got {type(self.combined_cashflows).__name__}"
            )
        validate_cashflow_dataframe(self.combined_cashflows)

        expected_rows = (
            len(self.baseline_result.engine_result.cashflows)
            + len(self.asset_cashflows)
        )
        if len(self.combined_cashflows) != expected_rows:
            raise ValueError(
                "combined_cashflows must have exactly baseline cashflow rows "
                "+ asset_cashflow rows "
                f"({len(self.combined_cashflows)} != {expected_rows})"
            )

        if not isinstance(self.combined_annual_cashflows, pd.DataFrame):
            raise TypeError(
                f"combined_annual_cashflows must be a pandas DataFrame, "
                f"got {type(self.combined_annual_cashflows).__name__}"
            )
        validate_annual_cashflow_dataframe(self.combined_annual_cashflows)

        for fname in (
            "combined_liquidity_inflection_year_structural",
            "combined_liquidity_inflection_year_net",
        ):
            value = getattr(self, fname)
            if isinstance(value, bool):
                raise TypeError(f"{fname} must not be bool")
            if value is not None and not isinstance(value, int):
                raise TypeError(
                    f"{fname} must be int or None, got {type(value).__name__}"
                )


def run_stage1_baseline_with_bond_overlay(
    *,
    scenario_id: str = "stage1_baseline_with_bond_overlay",
    horizon_years: int = 12,
    start_year: int = 2026,
    contribution_multiplier: float = 1.4,
    active_interest_rate: float = 0.0176,
    retired_interest_rate: float = 0.0176,
    technical_interest_rate: float = 0.0176,
    valuation_terminal_age: int = 90,
    target_funding_ratio: float = 1.076,
    annual_asset_return: float = 0.0,
    bond_contract_id: str = "BOND_1",
    bond_start_year: int | None = None,
    bond_maturity_year: int | None = None,
    bond_nominal_value: float = 100000.0,
    bond_annual_coupon_rate: float = 0.02,
    bond_currency: str = "CHF",
    include_purchase_event: bool = False,
) -> AssetOverlayResult:
    """Run the baseline and overlay deterministic ACTUS-style bond cashflows."""
    baseline_result = run_stage1_baseline(
        scenario_id=scenario_id,
        horizon_years=horizon_years,
        start_year=start_year,
        contribution_multiplier=contribution_multiplier,
        active_interest_rate=active_interest_rate,
        retired_interest_rate=retired_interest_rate,
        technical_interest_rate=technical_interest_rate,
        valuation_terminal_age=valuation_terminal_age,
        target_funding_ratio=target_funding_ratio,
        annual_asset_return=annual_asset_return,
        output_dir=None,
    )

    effective_bond_start_year = (
        start_year if bond_start_year is None else bond_start_year
    )
    if bond_maturity_year is None:
        if horizon_years == 0:
            effective_bond_maturity_year = start_year + 1
        else:
            effective_bond_maturity_year = start_year + min(horizon_years, 2)
    else:
        effective_bond_maturity_year = bond_maturity_year

    asset_cashflows = build_fixed_rate_bond_cashflow_dataframe(
        contract_id=bond_contract_id,
        start_year=effective_bond_start_year,
        maturity_year=effective_bond_maturity_year,
        nominal_value=bond_nominal_value,
        annual_coupon_rate=bond_annual_coupon_rate,
        currency=bond_currency,
        include_purchase_event=include_purchase_event,
    )
    validate_cashflow_dataframe(asset_cashflows)

    combined_cashflows = pd.concat(
        [baseline_result.engine_result.cashflows, asset_cashflows],
        ignore_index=True,
    )
    combined_cashflows = combined_cashflows.sort_values(
        ["time", "source", "contractId", "type"],
        ignore_index=True,
    )
    validate_cashflow_dataframe(combined_cashflows)

    combined_annual_cashflows = summarize_cashflows_by_year(combined_cashflows)
    validate_annual_cashflow_dataframe(combined_annual_cashflows)

    inflection_structural = find_liquidity_inflection_year(
        combined_annual_cashflows,
        use_structural=True,
    )
    inflection_net = find_liquidity_inflection_year(
        combined_annual_cashflows,
        use_structural=False,
    )

    return AssetOverlayResult(
        baseline_result=baseline_result,
        asset_cashflows=asset_cashflows,
        combined_cashflows=combined_cashflows,
        combined_annual_cashflows=combined_annual_cashflows,
        combined_liquidity_inflection_year_structural=inflection_structural,
        combined_liquidity_inflection_year_net=inflection_net,
    )
