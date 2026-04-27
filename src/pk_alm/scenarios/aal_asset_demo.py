"""Pension fund combined cashflow demo using the AAL/ACTUS asset boundary.

This module combines deterministic BVG liability cashflows from the Stage-1
baseline with AAL/ACTUS asset-boundary fallback cashflows. It demonstrates
the shared CashflowRecord schema as an integration contract between the
liability side (BVG) and the asset side (AAL/ACTUS).

Design constraints:
- Does NOT call PublicActusService or any network service.
- Does NOT modify run_stage1_baseline(...) or its default outputs.
- Does NOT make AAL a hard dependency (offline fallback always available).
- The seven default Stage-1 CSV outputs are unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from pk_alm.adapters.aal_asset_boundary import (
    DEFAULT_PAM_CONTRACT_ID,
    DEFAULT_PAM_COUPON_RATE,
    DEFAULT_PAM_CURRENCY,
    DEFAULT_PAM_NOMINAL_VALUE,
    get_aal_asset_boundary_fallback_cashflows,
)
from pk_alm.analytics.cashflows import (
    find_liquidity_inflection_year,
    summarize_cashflows_by_year,
    validate_annual_cashflow_dataframe,
)
from pk_alm.cashflows.schema import validate_cashflow_dataframe
from pk_alm.scenarios.stage1_baseline import Stage1BaselineResult, run_stage1_baseline


@dataclass(frozen=True)
class PensionFundAALAssetDemoResult:
    """Result container for one BVG + AAL/ACTUS asset boundary combined run."""

    baseline_result: Stage1BaselineResult
    aal_cashflows: pd.DataFrame
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

        if not isinstance(self.aal_cashflows, pd.DataFrame):
            raise TypeError(
                f"aal_cashflows must be a pandas DataFrame, "
                f"got {type(self.aal_cashflows).__name__}"
            )
        validate_cashflow_dataframe(self.aal_cashflows)
        if not self.aal_cashflows.empty and not (
            self.aal_cashflows["source"] == "ACTUS"
        ).all():
            raise ValueError('aal_cashflows source values must all be "ACTUS"')

        if not isinstance(self.combined_cashflows, pd.DataFrame):
            raise TypeError(
                f"combined_cashflows must be a pandas DataFrame, "
                f"got {type(self.combined_cashflows).__name__}"
            )
        validate_cashflow_dataframe(self.combined_cashflows)

        expected_rows = (
            len(self.baseline_result.engine_result.cashflows)
            + len(self.aal_cashflows)
        )
        if len(self.combined_cashflows) != expected_rows:
            raise ValueError(
                "combined_cashflows must have exactly baseline cashflow rows "
                f"+ aal_cashflow rows "
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


def run_pension_fund_aal_asset_demo(
    *,
    scenario_id: str = "pension_fund_aal_asset_demo",
    horizon_years: int = 12,
    start_year: int = 2026,
    contribution_multiplier: float = 1.4,
    active_interest_rate: float = 0.0176,
    retired_interest_rate: float = 0.0176,
    technical_interest_rate: float = 0.0176,
    valuation_terminal_age: int = 90,
    target_funding_ratio: float = 1.076,
    annual_asset_return: float = 0.0,
    aal_contract_id: str = DEFAULT_PAM_CONTRACT_ID,
    aal_start_year: int | None = None,
    aal_maturity_year: int | None = None,
    aal_nominal_value: float = DEFAULT_PAM_NOMINAL_VALUE,
    aal_coupon_rate: float = DEFAULT_PAM_COUPON_RATE,
    aal_currency: str = DEFAULT_PAM_CURRENCY,
    aal_include_purchase_event: bool = False,
) -> PensionFundAALAssetDemoResult:
    """Run Stage-1 baseline and combine with AAL/ACTUS asset boundary cashflows.

    The AAL/ACTUS cashflows come from the offline fallback (no network call,
    no AAL installation required). The result exposes the combined cashflow
    DataFrame and annual summary so callers can inspect the unified pension
    fund cashflow view.
    """
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

    effective_aal_start = start_year if aal_start_year is None else aal_start_year
    if aal_maturity_year is None:
        effective_aal_maturity = (
            start_year + 1 if horizon_years == 0 else start_year + min(horizon_years, 2)
        )
    else:
        effective_aal_maturity = aal_maturity_year

    aal_cashflows = get_aal_asset_boundary_fallback_cashflows(
        contract_id=aal_contract_id,
        start_year=effective_aal_start,
        maturity_year=effective_aal_maturity,
        nominal_value=aal_nominal_value,
        annual_coupon_rate=aal_coupon_rate,
        currency=aal_currency,
        include_purchase_event=aal_include_purchase_event,
    )
    validate_cashflow_dataframe(aal_cashflows)

    combined_cashflows = pd.concat(
        [baseline_result.engine_result.cashflows, aal_cashflows],
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
        combined_annual_cashflows, use_structural=True
    )
    inflection_net = find_liquidity_inflection_year(
        combined_annual_cashflows, use_structural=False
    )

    return PensionFundAALAssetDemoResult(
        baseline_result=baseline_result,
        aal_cashflows=aal_cashflows,
        combined_cashflows=combined_cashflows,
        combined_annual_cashflows=combined_annual_cashflows,
        combined_liquidity_inflection_year_structural=inflection_structural,
        combined_liquidity_inflection_year_net=inflection_net,
    )
