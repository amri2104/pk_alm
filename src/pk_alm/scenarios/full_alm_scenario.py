"""Full ALM scenario combining BVG liability and AAL/ACTUS asset cashflows.

This scenario glues the two engines:

- BVG Liability Engine via :func:`run_stage1_baseline`.
- AAL Asset Engine via :func:`run_aal_asset_engine`.

It concatenates both cashflow streams in the canonical CashflowRecord schema
and recomputes annual cashflow analytics on the combined view. The default
asset path is the AAL strategic engine; the fallback path is allowed only
when explicitly requested via ``generation_mode="fallback"``. There is no
silent fallback.

The scenario does not modify ``run_stage1_baseline(...)``, the BVG modules,
or the seven default Stage-1 CSV outputs.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from pk_alm.adapters.aal_asset_portfolio import AALAssetContractSpec
from pk_alm.analytics.cashflows import (
    summarize_cashflows_by_year,
    validate_annual_cashflow_dataframe,
)
from pk_alm.assets.aal_engine import (
    VALID_GENERATION_MODES,
    AALAssetEngineResult,
    run_aal_asset_engine,
)
from pk_alm.cashflows.schema import validate_cashflow_dataframe
from pk_alm.scenarios.stage1_baseline import (
    Stage1BaselineResult,
    run_stage1_baseline,
)

_COMBINED_SORT_COLUMNS = ("time", "source", "contractId", "type")


@dataclass(frozen=True)
class FullALMScenarioResult:
    """Result container for one Full ALM scenario run."""

    stage1_result: Stage1BaselineResult
    aal_asset_result: AALAssetEngineResult
    bvg_cashflows: pd.DataFrame
    asset_cashflows: pd.DataFrame
    combined_cashflows: pd.DataFrame
    annual_cashflows: pd.DataFrame
    generation_mode: str

    def __post_init__(self) -> None:
        if not isinstance(self.stage1_result, Stage1BaselineResult):
            raise TypeError(
                f"stage1_result must be Stage1BaselineResult, "
                f"got {type(self.stage1_result).__name__}"
            )
        if not isinstance(self.aal_asset_result, AALAssetEngineResult):
            raise TypeError(
                f"aal_asset_result must be AALAssetEngineResult, "
                f"got {type(self.aal_asset_result).__name__}"
            )

        for fname in ("bvg_cashflows", "asset_cashflows", "combined_cashflows"):
            value = getattr(self, fname)
            if not isinstance(value, pd.DataFrame):
                raise TypeError(
                    f"{fname} must be a pandas DataFrame, "
                    f"got {type(value).__name__}"
                )
            validate_cashflow_dataframe(value)

        if not self.asset_cashflows.empty and not (
            self.asset_cashflows["source"] == "ACTUS"
        ).all():
            raise ValueError('asset_cashflows source values must all be "ACTUS"')

        expected_rows = len(self.bvg_cashflows) + len(self.asset_cashflows)
        if len(self.combined_cashflows) != expected_rows:
            raise ValueError(
                "combined_cashflows must have exactly "
                "len(bvg_cashflows) + len(asset_cashflows) rows "
                f"({len(self.combined_cashflows)} != {expected_rows})"
            )

        if not isinstance(self.annual_cashflows, pd.DataFrame):
            raise TypeError(
                f"annual_cashflows must be a pandas DataFrame, "
                f"got {type(self.annual_cashflows).__name__}"
            )
        validate_annual_cashflow_dataframe(self.annual_cashflows)

        if self.generation_mode not in VALID_GENERATION_MODES:
            raise ValueError(
                f"generation_mode must be one of {VALID_GENERATION_MODES}, "
                f"got {self.generation_mode!r}"
            )
        if self.generation_mode != self.aal_asset_result.generation_mode:
            raise ValueError(
                "generation_mode must match aal_asset_result.generation_mode "
                f"({self.generation_mode!r} != "
                f"{self.aal_asset_result.generation_mode!r})"
            )


def run_full_alm_scenario(
    *,
    scenario_id: str = "full_alm_scenario",
    horizon_years: int = 12,
    start_year: int = 2026,
    contribution_multiplier: float = 1.4,
    active_interest_rate: float = 0.0176,
    retired_interest_rate: float = 0.0176,
    technical_interest_rate: float = 0.0176,
    valuation_terminal_age: int = 90,
    target_funding_ratio: float = 1.076,
    annual_asset_return: float = 0.0,
    asset_specs: tuple[AALAssetContractSpec, ...]
    | list[AALAssetContractSpec]
    | None = None,
    generation_mode: str = "aal",
) -> FullALMScenarioResult:
    """Run the BVG liability engine and the AAL Asset Engine and combine results.

    The default asset generation mode is ``"aal"`` (the strategic main
    path). To run offline without AAL, the caller must pass
    ``generation_mode="fallback"`` explicitly. Silent fallback is not
    available.
    """
    if generation_mode not in VALID_GENERATION_MODES:
        raise ValueError(
            f"generation_mode must be one of {VALID_GENERATION_MODES}, "
            f"got {generation_mode!r}"
        )

    stage1_result = run_stage1_baseline(
        scenario_id=scenario_id,
        horizon_years=horizon_years,
        start_year=start_year,
        active_interest_rate=active_interest_rate,
        retired_interest_rate=retired_interest_rate,
        technical_interest_rate=technical_interest_rate,
        contribution_multiplier=contribution_multiplier,
        valuation_terminal_age=valuation_terminal_age,
        target_funding_ratio=target_funding_ratio,
        annual_asset_return=annual_asset_return,
        output_dir=None,
    )

    aal_asset_result = run_aal_asset_engine(
        specs=asset_specs,
        generation_mode=generation_mode,
    )

    bvg_cashflows = stage1_result.engine_result.cashflows
    asset_cashflows = aal_asset_result.cashflows

    combined_cashflows = pd.concat(
        [bvg_cashflows, asset_cashflows],
        ignore_index=True,
    )
    combined_cashflows = combined_cashflows.sort_values(
        list(_COMBINED_SORT_COLUMNS),
        ignore_index=True,
    )
    validate_cashflow_dataframe(combined_cashflows)

    annual_cashflows = summarize_cashflows_by_year(combined_cashflows)
    validate_annual_cashflow_dataframe(annual_cashflows)

    return FullALMScenarioResult(
        stage1_result=stage1_result,
        aal_asset_result=aal_asset_result,
        bvg_cashflows=bvg_cashflows,
        asset_cashflows=asset_cashflows,
        combined_cashflows=combined_cashflows,
        annual_cashflows=annual_cashflows,
        generation_mode=generation_mode,
    )
