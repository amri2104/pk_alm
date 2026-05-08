"""Advanced Goal-1 ALM workflow for the Streamlit cockpit.

This module is a workflow adapter over existing engines and analytics. It
converts analyst-facing tables into current domain objects, runs frozen BVG
projection/valuation layers, optionally calls the live AAL asset engine, and
writes dashboard-ready CSV/PNG outputs.
"""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from pk_alm.actus_asset_engine.aal_asset_portfolio import (
    make_csh_contract_config,
    make_pam_contract_config,
    make_stk_contract_config_from_nominal,
)
from pk_alm.actus_asset_engine.contract_config import (
    AALContractConfig,
    validate_aal_contract_configs,
)
from pk_alm.alm_analytics_engine.cashflows import (
    find_liquidity_inflection_year,
    summarize_cashflows_by_year,
)
from pk_alm.alm_analytics_engine.funding import build_funding_ratio_trajectory
from pk_alm.alm_analytics_engine.funding_summary import (
    funding_summary_to_dataframe,
    summarize_funding_ratio,
)
from pk_alm.actus_asset_engine.actus_trajectory import compute_actus_asset_trajectory
from pk_alm.actus_asset_engine.deterministic import build_deterministic_asset_trajectory
from pk_alm.actus_asset_engine.simulation_settings import AALSimulationSettings
from pk_alm.bvg_liability_engine.assumptions import (
    BVGAssumptions,
    FlatRateCurve,
    MortalityAssumptions,
    RateCurve,
)
from pk_alm.bvg_liability_engine.assumptions.rate_curves import (
    expand as expand_curve,
    from_dynamic_parameter,
)
from pk_alm.bvg_liability_engine.domain_models.cohorts import ActiveCohort, RetiredCohort
from pk_alm.bvg_liability_engine.orchestration import BVGEngineResult, run_bvg_engine
from pk_alm.bvg_liability_engine.population_dynamics.entry_dynamics import EntryAssumptions
from pk_alm.bvg_liability_engine.population_dynamics.entry_policies import FixedEntryPolicy
from pk_alm.bvg_liability_engine.actuarial_assumptions.mortality import (
    DEFAULT_EK0105_TABLE_ID,
    EKM_0105,
    EKF_0105,
    MORTALITY_MODE_EK0105,
    MORTALITY_MODE_OFF,
    MortalityTable,
    expected_pension_payment,
    load_ek0105_table,
    survival_factor,
)
from pk_alm.bvg_liability_engine.actuarial_assumptions.mortality_valuation import value_portfolio_state_stage2b
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.bvg_liability_engine.pension_logic.valuation_dynamic import value_portfolio_states_dynamic
from pk_alm.cashflows.schema import CASHFLOW_COLUMNS, validate_cashflow_dataframe
from pk_alm.scenarios.stage2d_stochastic import run_stage2d_stochastic
from pk_alm.workflows.stage_app_workflow import (
    MODE_CORE,
    MODE_DYNAMIC_PARAMETERS,
    MODE_MORTALITY,
    MODE_POPULATION,
    MODE_STOCHASTIC_RATES,
    PROTECTED_OUTPUT_DIRS,
    run_stage,
)

AssetEngineMode = Literal["actus", "deterministic_proxy"]
ScenarioPreset = Literal[
    "Baseline",
    "Interest +100bp",
    "Interest -100bp",
    "Equity -20%",
    "Real Estate -15%",
    "Combined",
]

GOAL1_ADVANCED_OUTPUT_DIR = Path("outputs/streamlit_goal1_advanced")
STAGE_COMPARISON_OUTPUT_DIR = Path("outputs/streamlit_stage_comparison")

ALLOCATION_COLUMNS = ("asset_class", "weight")
BOND_COLUMNS = ("contract_id", "notional", "coupon_rate", "maturity_years", "currency")
ACTIVE_COLUMNS = (
    "cohort_id",
    "age",
    "count",
    "gross_salary",
    "savings_capital",
    "gender",
)
RETIREE_COLUMNS = (
    "cohort_id",
    "age",
    "count",
    "annual_pension",
    "retirement_capital",
    "gender",
)

DEFAULT_ALLOCATION_TABLE = pd.DataFrame(
    [
        # Calibrated to Complementa Risiko Check-up 2024 sector averages
        # (bonds 30.9%, equities 28%, real_estate 22.5%, alternatives 10%, cash ~8.6%)
        {"asset_class": "bonds", "weight": 0.31},
        {"asset_class": "equities", "weight": 0.28},
        {"asset_class": "real_estate", "weight": 0.23},
        {"asset_class": "alternatives", "weight": 0.10},
        {"asset_class": "cash", "weight": 0.08},
    ],
    columns=list(ALLOCATION_COLUMNS),
)

DEFAULT_BOND_TABLE = pd.DataFrame(
    [
        {
            "contract_id": "COCKPIT_BOND_3Y",
            "notional": 1.0,
            "coupon_rate": 0.015,
            "maturity_years": 3,
            "currency": "CHF",
        },
        {
            "contract_id": "COCKPIT_BOND_7Y",
            "notional": 1.0,
            "coupon_rate": 0.018,
            "maturity_years": 7,
            "currency": "CHF",
        },
        {
            "contract_id": "COCKPIT_BOND_12Y",
            "notional": 1.0,
            "coupon_rate": 0.021,
            "maturity_years": 12,
            "currency": "CHF",
        },
    ],
    columns=list(BOND_COLUMNS),
)

# Cohort counts scaled to a mid-sized Swiss PK (~285 active, ~70 retired,
# rentnerquote ~20% — within Complementa 2024 norm of 15-22%).
DEFAULT_ACTIVE_TABLE = pd.DataFrame(
    [
        {
            "cohort_id": "ACT_30",
            "age": 30,
            "count": 80,
            "gross_salary": 75_000.0,
            "savings_capital": 35_000.0,
            "gender": "mixed",
        },
        {
            "cohort_id": "ACT_40",
            "age": 40,
            "count": 100,
            "gross_salary": 88_000.0,
            "savings_capital": 130_000.0,
            "gender": "mixed",
        },
        {
            "cohort_id": "ACT_50",
            "age": 50,
            "count": 70,
            "gross_salary": 92_000.0,
            "savings_capital": 280_000.0,
            "gender": "mixed",
        },
        {
            "cohort_id": "ACT_60",
            "age": 60,
            "count": 35,
            "gross_salary": 90_000.0,
            "savings_capital": 480_000.0,
            "gender": "mixed",
        },
    ],
    columns=list(ACTIVE_COLUMNS),
)

DEFAULT_RETIREE_TABLE = pd.DataFrame(
    [
        {
            "cohort_id": "RET_68",
            "age": 68,
            "count": 30,
            "annual_pension": 32_000.0,
            "retirement_capital": 480_000.0,
            "gender": "mixed",
        },
        {
            "cohort_id": "RET_75",
            "age": 75,
            "count": 25,
            "annual_pension": 28_000.0,
            "retirement_capital": 320_000.0,
            "gender": "mixed",
        },
        {
            "cohort_id": "RET_82",
            "age": 82,
            "count": 15,
            "annual_pension": 24_000.0,
            "retirement_capital": 180_000.0,
            "gender": "female",
        },
    ],
    columns=list(RETIREE_COLUMNS),
)


@dataclass(frozen=True)
class Goal1AdvancedInput:
    """Input bundle for the advanced Goal-1 cockpit workflow."""

    allocation_table: pd.DataFrame
    bond_table: pd.DataFrame
    active_table: pd.DataFrame
    retiree_table: pd.DataFrame
    horizon_years: int = 12
    start_year: int = 2026
    target_funding_ratio: float = 1.076
    valuation_terminal_age: int = 95
    # BVG-Mindestzins 2024 was 1.25%; technical rates per Complementa 2024 ~1.76%.
    active_interest_rate: float | tuple[float, ...] = 0.0125
    retired_interest_rate: float = 0.0176
    technical_interest_rate: float | tuple[float, ...] = 0.0176
    # Gesetzlicher BVG-Mindestumwandlungssatz (Art. 14 BVG); Complementa effective ~5.19%.
    conversion_rate: float | tuple[float, ...] = 0.068
    contribution_multiplier: float = 1.4
    salary_growth_rate: float = 0.015
    turnover_rate: float = 0.04
    entry_count_per_year: int = 8
    mortality_mode: str = MORTALITY_MODE_EK0105
    mortality_table_id: str = DEFAULT_EK0105_TABLE_ID
    scenario_preset: ScenarioPreset = "Baseline"
    asset_engine_mode: AssetEngineMode = "actus"
    stochastic_enabled: bool = False
    model_active: str = "hull_white"
    model_technical: str = "hull_white"
    stochastic_asset_return: float = 0.025
    n_paths: int = 100
    seed: int = 42
    output_dir: Path = GOAL1_ADVANCED_OUTPUT_DIR


@dataclass(frozen=True)
class Goal1AdvancedResult:
    """Outputs produced by the advanced Goal-1 cockpit workflow."""

    output_dir: Path
    input: Goal1AdvancedInput
    initial_state: BVGPortfolioState
    asset_contracts: tuple[AALContractConfig, ...]
    engine_result: BVGEngineResult
    cashflows: pd.DataFrame
    valuation_snapshots: pd.DataFrame
    annual_cashflows: pd.DataFrame
    asset_snapshots: pd.DataFrame
    funding_ratio_trajectory: pd.DataFrame
    funding_summary: pd.DataFrame
    kpi_summary: pd.DataFrame
    cashflow_by_source: pd.DataFrame
    net_cashflow: pd.DataFrame
    validation_checks: pd.DataFrame
    stochastic_summary: pd.DataFrame | None
    output_paths: dict[str, Path]
    plot_paths: dict[str, Path]


@dataclass(frozen=True)
class StageComparisonResult:
    """Stage comparison package for the cockpit."""

    output_dir: Path
    comparison_table: pd.DataFrame
    stage_explanations: pd.DataFrame
    output_paths: dict[str, Path]


def run_goal1_advanced_alm(input_data: Goal1AdvancedInput) -> Goal1AdvancedResult:
    """Run the advanced Goal-1 ALM workflow and write dashboard artifacts."""
    _reject_protected_output_dir(input_data.output_dir)
    out_path = Path(input_data.output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    shocked = _apply_scenario_preset(input_data)
    initial_state = population_tables_to_portfolio_state(
        shocked.active_table,
        shocked.retiree_table,
    )

    curve_horizon = max(shocked.horizon_years + 1, 1)
    assumptions = BVGAssumptions(
        start_year=shocked.start_year,
        horizon_years=shocked.horizon_years,
        retirement_age=65,
        valuation_terminal_age=shocked.valuation_terminal_age,
        active_crediting_rate=_curve_from_rate_input(
            shocked.active_interest_rate,
            start_year=shocked.start_year,
            horizon_years=curve_horizon,
        ),
        retired_interest_rate=FlatRateCurve(shocked.retired_interest_rate),
        technical_discount_rate=_curve_from_rate_input(
            shocked.technical_interest_rate,
            start_year=shocked.start_year,
            horizon_years=curve_horizon,
        ),
        economic_discount_rate=_curve_from_rate_input(
            shocked.technical_interest_rate,
            start_year=shocked.start_year,
            horizon_years=curve_horizon,
        ),
        salary_growth_rate=FlatRateCurve(shocked.salary_growth_rate),
        conversion_rate=_curve_from_rate_input(
            shocked.conversion_rate,
            start_year=shocked.start_year,
            horizon_years=curve_horizon,
        ),
        turnover_rate=shocked.turnover_rate,
        capital_withdrawal_fraction=0.35,
        contribution_multiplier=shocked.contribution_multiplier,
        mortality=MortalityAssumptions(mode="off"),
        entry_policy=FixedEntryPolicy(
            EntryAssumptions(
                entry_count_per_year=shocked.entry_count_per_year
            )
        ),
    )
    stage2c_engine = run_bvg_engine(
        initial_state=initial_state,
        assumptions=assumptions,
    )

    base_valuation = value_portfolio_states_dynamic(
        stage2c_engine.portfolio_states,
        shocked.technical_interest_rate,
        shocked.valuation_terminal_age,
    )
    mortality_table = (
        None
        if shocked.mortality_mode == MORTALITY_MODE_OFF
        else load_ek0105_table(shocked.mortality_table_id)
    )
    cashflows = _apply_mortality_to_cashflows(
        stage2c_engine,
        mortality_table,
        shocked.start_year,
    )
    valuation_snapshots = _build_mortality_aware_valuation(
        stage2c_engine.portfolio_states,
        shocked.technical_interest_rate,
        shocked.valuation_terminal_age,
        shocked.mortality_mode,
        mortality_table,
    )
    annual_cashflows = summarize_cashflows_by_year(cashflows)
    valuation_for_funding = _valuation_for_funding_schema(valuation_snapshots)

    asset_contracts = asset_table_to_contract_configs(
        shocked.allocation_table,
        shocked.bond_table,
        start_year=shocked.start_year,
        target_assets=float(valuation_for_funding.iloc[0]["total_stage1_liability"])
        * shocked.target_funding_ratio,
        horizon_years=shocked.horizon_years,
    )
    if shocked.asset_engine_mode == "actus":
        asset_snapshots, combined_cashflows = _build_actus_assets_and_cashflows(
            asset_contracts=asset_contracts,
            liability_cashflows=cashflows,
            valuation_for_funding=valuation_for_funding,
            target_funding_ratio=shocked.target_funding_ratio,
            horizon_years=shocked.horizon_years,
        )
        cashflows_for_analytics = combined_cashflows
        annual_cashflows = summarize_cashflows_by_year(cashflows_for_analytics)
    else:
        # Conservative long-run nominal asset return; Complementa 20Y avg ~3.7%.
        # Income (bond coupons + STK dividends) is added separately via
        # ASSUMPTION cashflows below to avoid double-counting yield.
        asset_snapshots = build_deterministic_asset_trajectory(
            valuation_for_funding,
            annual_cashflows,
            target_funding_ratio=shocked.target_funding_ratio,
            annual_return_rate=0.025,
            start_year=shocked.start_year,
        )
        # Augment with ASSUMPTION-source income so Income Yield KPI and
        # source-decomposition charts have non-bond income visible even
        # when the live ACTUS engine is not used. PAM coupons are also
        # synthesised here because deterministic-proxy never runs ACTUS;
        # in ACTUS mode this branch is skipped, so no double-counting.
        assumption_cashflows = _build_assumption_income_cashflows(
            asset_contracts,
            horizon_years=shocked.horizon_years,
            start_year=shocked.start_year,
            include_pam_coupons=True,
        )
        if assumption_cashflows.empty:
            cashflows_for_analytics = cashflows
        else:
            cashflows_for_analytics = pd.concat(
                [cashflows, assumption_cashflows], ignore_index=True
            ).sort_values(
                ["time", "source", "contractId", "type"], ignore_index=True
            )
            validate_cashflow_dataframe(cashflows_for_analytics)
            annual_cashflows = summarize_cashflows_by_year(cashflows_for_analytics)

    funding_ratio = build_funding_ratio_trajectory(
        asset_snapshots,
        valuation_for_funding,
    )
    funding_summary = funding_summary_to_dataframe(
        summarize_funding_ratio(
            funding_ratio,
            target_funding_ratio=shocked.target_funding_ratio,
        )
    )
    cashflow_by_source = _build_cashflow_by_source_table(cashflows_for_analytics)
    net_cashflow = annual_cashflows[
        [
            "reporting_year",
            "contribution_cashflow",
            "pension_payment_cashflow",
            "capital_withdrawal_cashflow",
            "other_cashflow",
            "net_cashflow",
            "structural_net_cashflow",
        ]
    ].copy(deep=True)
    kpi_summary = _build_goal1_kpi_summary(
        funding_ratio,
        annual_cashflows,
        valuation_snapshots,
        cashflows_for_analytics,
        stochastic_summary=None,
    )
    stochastic_summary = None
    if shocked.stochastic_enabled:
        stochastic_summary = _run_stochastic_sidecar(shocked)
        kpi_summary = _build_goal1_kpi_summary(
            funding_ratio,
            annual_cashflows,
            valuation_snapshots,
            cashflows_for_analytics,
            stochastic_summary=stochastic_summary,
        )
    validation_checks = _build_validation_checks(
        allocation_table=shocked.allocation_table,
        funding_ratio=funding_ratio,
        kpi_summary=kpi_summary,
        valuation_snapshots=valuation_snapshots,
        initial_state=initial_state,
    )

    output_paths = _write_goal1_csv_outputs(
        out_path,
        {
            "cashflows.csv": cashflows_for_analytics,
            "liability_cashflows.csv": cashflows,
            "valuation_snapshots.csv": valuation_snapshots,
            "annual_cashflows.csv": annual_cashflows,
            "asset_snapshots.csv": asset_snapshots,
            "funding_ratio_trajectory.csv": funding_ratio,
            "funding_summary.csv": funding_summary,
            "kpi_summary.csv": kpi_summary,
            "cashflow_by_source.csv": cashflow_by_source,
            "net_cashflow.csv": net_cashflow,
            "validation_checks.csv": validation_checks,
        },
    )
    if stochastic_summary is not None:
        output_paths["stochastic_summary"] = _write_csv(
            stochastic_summary,
            out_path / "stochastic_summary.csv",
        )
    plot_paths = _write_goal1_plots(
        out_path / "plots",
        funding_ratio=funding_ratio,
        net_cashflow=net_cashflow,
        cashflow_by_source=cashflow_by_source,
    )

    return Goal1AdvancedResult(
        output_dir=out_path,
        input=shocked,
        initial_state=initial_state,
        asset_contracts=asset_contracts,
        engine_result=stage2c_engine,
        cashflows=cashflows_for_analytics,
        valuation_snapshots=valuation_snapshots,
        annual_cashflows=annual_cashflows,
        asset_snapshots=asset_snapshots,
        funding_ratio_trajectory=funding_ratio,
        funding_summary=funding_summary,
        kpi_summary=kpi_summary,
        cashflow_by_source=cashflow_by_source,
        net_cashflow=net_cashflow,
        validation_checks=validation_checks,
        stochastic_summary=stochastic_summary,
        output_paths=output_paths,
        plot_paths=plot_paths,
    )


def run_goal1_stage_comparison(
    *,
    common_kwargs: dict[str, object] | None = None,
    output_dir: str | Path = STAGE_COMPARISON_OUTPUT_DIR,
) -> StageComparisonResult:
    """Run/load reference backend stages and write a compact comparison table."""
    out_path = Path(output_dir)
    _reject_protected_output_dir(out_path)
    out_path.mkdir(parents=True, exist_ok=True)
    kwargs = {} if common_kwargs is None else dict(common_kwargs)
    rows: list[dict[str, object]] = []
    for mode_id, label, adds in (
        (MODE_CORE, "Core", "Stage-1 deterministic baseline"),
        (MODE_POPULATION, "Population", "Entries, turnover, salary growth"),
        (MODE_MORTALITY, "Mortality", "EK0105 retiree expected-value layer"),
        (MODE_DYNAMIC_PARAMETERS, "Dynamic Parameters", "UWS and rate paths"),
    ):
        try:
            result = run_stage(mode_id, **kwargs)
            rows.append(_comparison_row(label, adds, result.csv_outputs))
        except Exception as exc:
            rows.append(_comparison_error_row(label, adds, exc))
    try:
        stochastic = run_stage(MODE_STOCHASTIC_RATES, **{**kwargs, "n_paths": 10})
        rows.append(_comparison_row("Stochastic", "Rate-path distribution", stochastic.csv_outputs))
    except Exception as exc:
        rows.append(_comparison_error_row("Stochastic", "Rate-path distribution", exc))

    comparison = pd.DataFrame(rows)
    explanations = pd.DataFrame(
        [
            {"stage": row["stage"], "adds": row["adds"], "status": row["status"]}
            for row in rows
        ]
    )
    output_paths = {
        "stage_comparison": _write_csv(comparison, out_path / "stage_comparison.csv"),
        "stage_explanations": _write_csv(explanations, out_path / "stage_explanations.csv"),
    }
    return StageComparisonResult(out_path, comparison, explanations, output_paths)


def asset_table_to_contract_configs(
    allocation_table: pd.DataFrame,
    bond_table: pd.DataFrame,
    *,
    start_year: int,
    target_assets: float,
    horizon_years: int = 12,
) -> tuple[AALContractConfig, ...]:
    """Convert cockpit allocation/bond tables into ACTUS contract configs."""
    allocations = _allocation_weights(allocation_table)
    target = _validate_real(target_assets, "target_assets", min_value=0.0, strict=True)
    start = _validate_int(start_year, "start_year", min_value=2000)
    horizon = _validate_int(horizon_years, "horizon_years", min_value=1)
    contracts: list[AALContractConfig] = []

    bond_bucket = target * allocations.get("bonds", 0.0)
    bonds = _validate_columns(bond_table, BOND_COLUMNS, "bond_table")
    total_bond_notional = float(bonds["notional"].sum()) if not bonds.empty else 0.0
    if bond_bucket > 0 and total_bond_notional <= 0:
        raise ValueError("bond notional total must be > 0 when bond weight is positive")
    for _, row in bonds.iterrows():
        maturity_years = _validate_int(row["maturity_years"], "maturity_years", min_value=1)
        notional = _validate_real(row["notional"], "notional", min_value=0.0, strict=True)
        scaled_notional = bond_bucket * notional / total_bond_notional
        contracts.append(
            make_pam_contract_config(
                contract_id=str(row["contract_id"]).strip(),
                start_year=start,
                maturity_year=start + maturity_years,
                nominal_value=scaled_notional,
                coupon_rate=_validate_real(
                    row["coupon_rate"], "coupon_rate", min_value=0.0
                ),
                currency=str(row["currency"]).strip().upper(),
            )
        )
    for asset_class, dividend_yield, growth in (
        ("equities", 0.025, 0.04),
        ("real_estate", 0.035, 0.02),
        ("alternatives", 0.0, 0.03),
    ):
        nominal = target * allocations.get(asset_class, 0.0)
        if nominal > 0:
            contracts.append(
                _stk_contract_config(
                    asset_class, start, nominal, dividend_yield, growth, horizon
                )
            )
    cash_nominal = target * allocations.get("cash", 0.0)
    if cash_nominal > 0:
        contracts.append(
            make_csh_contract_config(
                contract_id="COCKPIT_CASH",
                start_year=start,
                nominal_value=cash_nominal,
                currency="CHF",
            )
        )
    return validate_aal_contract_configs(tuple(contracts))


def population_tables_to_portfolio_state(
    active_table: pd.DataFrame,
    retiree_table: pd.DataFrame,
) -> BVGPortfolioState:
    """Convert cockpit population tables into a BVGPortfolioState."""
    active = _validate_columns(active_table, ACTIVE_COLUMNS, "active_table")
    retired = _validate_columns(retiree_table, RETIREE_COLUMNS, "retiree_table")
    active_cohorts = tuple(
        ActiveCohort(
            cohort_id=str(row["cohort_id"]).strip(),
            age=_validate_int(row["age"], "age", min_value=0),
            count=_validate_int(row["count"], "count", min_value=0),
            gross_salary_per_person=_validate_real(
                row["gross_salary"], "gross_salary", min_value=0.0
            ),
            capital_active_per_person=_validate_real(
                row["savings_capital"], "savings_capital", min_value=0.0
            ),
        )
        for _, row in active.iterrows()
    )
    retired_cohorts = tuple(
        RetiredCohort(
            cohort_id=str(row["cohort_id"]).strip(),
            age=_validate_int(row["age"], "age", min_value=0),
            count=_validate_int(row["count"], "count", min_value=0),
            annual_pension_per_person=_validate_real(
                row["annual_pension"], "annual_pension", min_value=0.0
            ),
            capital_rente_per_person=_validate_real(
                row["retirement_capital"], "retirement_capital", min_value=0.0
            ),
        )
        for _, row in retired.iterrows()
    )
    return BVGPortfolioState(
        projection_year=0,
        active_cohorts=active_cohorts,
        retired_cohorts=retired_cohorts,
    )


def suggest_mortality_table_from_gender(retiree_table: pd.DataFrame) -> str:
    """Suggest a global EK0105 table from retiree gender metadata."""
    retired = _validate_columns(retiree_table, RETIREE_COLUMNS, "retiree_table")
    genders = [str(g).strip().lower() for g in retired["gender"]]
    male = sum(g.startswith("m") for g in genders)
    female = sum(g.startswith("f") or g.startswith("w") for g in genders)
    if male > female:
        return EKM_0105
    return EKF_0105


def load_goal1_csv_outputs(output_dir: str | Path) -> dict[str, pd.DataFrame]:
    root = Path(output_dir)
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): pd.read_csv(path)
        for path in sorted(root.rglob("*.csv"))
        if path.is_file()
    }


def load_goal1_plot_outputs(output_dir: str | Path) -> tuple[Path, ...]:
    root = Path(output_dir)
    if not root.exists():
        return ()
    return tuple(path for path in sorted(root.rglob("*.png")) if path.is_file())


def _apply_scenario_preset(input_data: Goal1AdvancedInput) -> Goal1AdvancedInput:
    if input_data.scenario_preset == "Baseline":
        return input_data
    delta = 0.0
    allocation = input_data.allocation_table.copy(deep=True)
    if input_data.scenario_preset in ("Interest +100bp",):
        delta = 0.01
    elif input_data.scenario_preset in ("Interest -100bp", "Combined"):
        delta = -0.01
    if input_data.scenario_preset in ("Equity -20%", "Combined"):
        allocation = _shock_weight_notional_proxy(allocation, "equities", 0.80)
    if input_data.scenario_preset in ("Real Estate -15%", "Combined"):
        allocation = _shock_weight_notional_proxy(allocation, "real_estate", 0.85)
    allocation = _renormalize_weights(allocation)
    if delta == 0.0:
        return Goal1AdvancedInput(**{**input_data.__dict__, "allocation_table": allocation})
    return Goal1AdvancedInput(
        **{
            **input_data.__dict__,
            "allocation_table": allocation,
            "active_interest_rate": _bump_parameter(input_data.active_interest_rate, delta),
            "retired_interest_rate": max(0.0, input_data.retired_interest_rate + delta),
            "technical_interest_rate": _bump_parameter(input_data.technical_interest_rate, delta),
        }
    )


def _bump_parameter(value: float | tuple[float, ...], delta: float) -> float | tuple[float, ...]:
    if isinstance(value, tuple):
        return tuple(max(0.0, float(v) + delta) for v in value)
    return max(0.0, float(value) + delta)


def _shock_weight_notional_proxy(df: pd.DataFrame, asset_class: str, factor: float) -> pd.DataFrame:
    result = df.copy(deep=True)
    mask = result["asset_class"].astype(str).str.lower() == asset_class
    result.loc[mask, "weight"] = result.loc[mask, "weight"].astype(float) * factor
    return result


def _renormalize_weights(df: pd.DataFrame) -> pd.DataFrame:
    total = float(df["weight"].sum())
    if total <= 0:
        return df
    result = df.copy(deep=True)
    result["weight"] = result["weight"].astype(float) / total
    return result


def _apply_mortality_to_cashflows(
    engine_result: BVGEngineResult,
    mortality_table: MortalityTable | None,
    start_year: int,
) -> pd.DataFrame:
    cashflows = engine_result.cashflows.copy(deep=True)
    if mortality_table is None:
        return cashflows
    origins = _retired_origins(engine_result.portfolio_states)
    for idx, row in cashflows.iterrows():
        if row["type"] != "RP":
            continue
        step = int(pd.Timestamp(row["time"]).year) - start_year
        state = engine_result.portfolio_states[step]
        cohort = next(c for c in state.retired_cohorts if c.cohort_id == row["contractId"])
        origin_year, origin_age = origins[cohort.cohort_id]
        survival = survival_factor(mortality_table, origin_age, max(0, step - origin_year))
        cashflows.at[idx, "payoff"] = expected_pension_payment(
            count=cohort.count,
            annual_pension_per_person=cohort.annual_pension_per_person,
            survival_probability=survival,
        )
    cashflows = cashflows[list(CASHFLOW_COLUMNS)]
    validate_cashflow_dataframe(cashflows)
    return cashflows


def _build_mortality_aware_valuation(
    states: tuple[BVGPortfolioState, ...],
    technical_interest_rate: float | tuple[float, ...] | RateCurve,
    valuation_terminal_age: int,
    mortality_mode: str,
    mortality_table: MortalityTable | None,
) -> pd.DataFrame:
    rates = _expand_rate_input(
        technical_interest_rate,
        start_year=0,
        horizon_years=len(states),
    )
    rows = [
        value_portfolio_state_stage2b(
            state,
            rates[i],
            valuation_terminal_age,
            mortality_mode,
            mortality_table,
        ).to_dict()
        for i, state in enumerate(states)
    ]
    return pd.DataFrame(rows)


def _curve_from_rate_input(
    value: float | tuple[float, ...] | RateCurve,
    *,
    start_year: int,
    horizon_years: int,
) -> RateCurve:
    if isinstance(value, RateCurve):
        return value
    return from_dynamic_parameter(
        value,
        start_year=start_year,
        horizon_years=horizon_years,
    )


def _expand_rate_input(
    value: float | tuple[float, ...] | RateCurve,
    *,
    start_year: int,
    horizon_years: int,
) -> tuple[float, ...]:
    curve = _curve_from_rate_input(
        value,
        start_year=start_year,
        horizon_years=horizon_years,
    )
    return expand_curve(
        curve,
        start_year=start_year,
        horizon_years=horizon_years,
    )


def _valuation_for_funding_schema(valuation: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "projection_year": valuation["projection_year"],
            "active_count_total": valuation["active_count_total"],
            "retired_count_total": valuation["retired_count_total"],
            "member_count_total": valuation["member_count_total"],
            "total_capital_active": valuation["total_capital_active"],
            "total_capital_rente": valuation["total_capital_rente"],
            "retiree_obligation_pv": valuation["mortality_weighted_retiree_obligation_pv"],
            "pensionierungsverlust": valuation["pensionierungsverlust"],
            "total_stage1_liability": valuation["total_stage2b_liability"],
            "technical_interest_rate": valuation["technical_interest_rate"],
            "valuation_terminal_age": valuation["valuation_terminal_age"],
            "currency": valuation["currency"],
        }
    )


def _build_actus_assets_and_cashflows(
    *,
    asset_contracts: tuple[AALContractConfig, ...],
    liability_cashflows: pd.DataFrame,
    valuation_for_funding: pd.DataFrame,
    target_funding_ratio: float,
    horizon_years: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    from pk_alm.actus_asset_engine.aal_engine import run_aal_asset_engine
    from pk_alm.scenarios.stage1_baseline import _asset_snapshots_from_actus_trajectory

    start_year = int(pd.to_datetime(liability_cashflows["time"]).dt.year.min())
    asset_result = run_aal_asset_engine(
        contracts=asset_contracts,
        settings=AALSimulationSettings(
            analysis_date=f"{start_year}-01-01T00:00:00",
            event_start_date=f"{start_year}-01-01T00:00:00",
            event_end_date=f"{start_year + horizon_years}-12-31T00:00:00",
            mode="validated",
            cashflow_cutoff_mode="from_status_date",
        ),
    )
    target_assets = float(valuation_for_funding.iloc[0]["total_stage1_liability"]) * target_funding_ratio
    zero_cash = compute_actus_asset_trajectory(
        asset_result.contracts,
        asset_result.cashflows,
        horizon_years,
        initial_cash=0.0,
    )
    initial_cash = target_assets - float(zero_cash.iloc[0]["closing_asset_value"])
    actus_trajectory = compute_actus_asset_trajectory(
        asset_result.contracts,
        asset_result.cashflows,
        horizon_years,
        initial_cash=initial_cash,
    )
    assumption_cashflows = _build_assumption_income_cashflows(
        asset_contracts, horizon_years=horizon_years, start_year=start_year
    )
    frames = [liability_cashflows, asset_result.cashflows]
    if not assumption_cashflows.empty:
        frames.append(assumption_cashflows)
    combined = pd.concat(frames, ignore_index=True)
    if not combined.empty:
        combined = combined.sort_values(["time", "source", "contractId", "type"], ignore_index=True)
    validate_cashflow_dataframe(combined)
    assets = _asset_snapshots_from_actus_trajectory(
        actus_trajectory,
        liability_cashflows,
        start_year=start_year,
        horizon_years=horizon_years,
    )
    return assets, combined


def _build_assumption_income_cashflows(
    asset_contracts: tuple[AALContractConfig, ...],
    *,
    horizon_years: int,
    start_year: int,
    include_pam_coupons: bool = False,
) -> pd.DataFrame:
    """Generate ASSUMPTION-source income cashflows (MANUAL).

    Public AAL/ACTUS server does not emit STK dividends or CSH temporal events.
    To make the income side of the cockpit realistic without changing the AAL
    engine, we synthesize annual income as `nominal * yield` for each STK
    with positive `dividend_yield`. Reported with source="MANUAL" so analysts
    can distinguish ACTUS-engine output from assumption-based income.

    When ``include_pam_coupons`` is True (deterministic-proxy mode only — must
    not be enabled when the live AAL engine runs, to avoid double-counting),
    each PAM config also emits annual coupons until maturity.
    """
    records: list[dict[str, object]] = []
    for contract in asset_contracts:
        terms = contract.terms
        if contract.contract_type == "STK":
            nominal = float(terms.get("notionalPrincipal", 0.0))
            dividend = float(terms.get("nextDividendPaymentAmount", 0.0))
            annual_yield = 0.0 if nominal <= 0.0 else dividend / nominal
            if annual_yield <= 0.0:
                continue
            if nominal <= 0.0:
                continue
            termination = pd.Timestamp(terms.get("terminationDate"))
            status = pd.Timestamp(terms.get("statusDate"))
            last_income_year = min(
                int(termination.year) - 1, start_year + horizon_years
            )
            for year in range(int(status.year), last_income_year + 1):
                records.append(
                    {
                        "contractId": contract.contract_id,
                        "time": pd.Timestamp(f"{year}-12-31"),
                        "type": "IP",
                        "payoff": nominal * annual_yield,
                        "nominalValue": nominal,
                        "currency": contract.currency,
                        "source": "MANUAL",
                    }
                )
        elif include_pam_coupons and contract.contract_type == "PAM":
            coupon_rate = float(terms.get("nominalInterestRate", 0.0))
            nominal = float(terms.get("notionalPrincipal", 0.0))
            if coupon_rate <= 0.0 or nominal <= 0.0:
                continue
            maturity = pd.Timestamp(terms.get("maturityDate"))
            status = pd.Timestamp(terms.get("statusDate"))
            last_coupon_year = min(
                int(maturity.year) - 1, start_year + horizon_years
            )
            for year in range(int(status.year), last_coupon_year + 1):
                records.append(
                    {
                        "contractId": contract.contract_id,
                        "time": pd.Timestamp(f"{year}-12-31"),
                        "type": "IP",
                        "payoff": nominal * coupon_rate,
                        "nominalValue": nominal,
                        "currency": contract.currency,
                        "source": "MANUAL",
                    }
                )
    if not records:
        return pd.DataFrame(columns=list(CASHFLOW_COLUMNS))
    df = pd.DataFrame(records, columns=list(CASHFLOW_COLUMNS))
    validate_cashflow_dataframe(df)
    return df


def _run_stochastic_sidecar(input_data: Goal1AdvancedInput) -> pd.DataFrame:
    result = run_stage2d_stochastic(
        horizon_years=input_data.horizon_years,
        start_year=input_data.start_year,
        n_paths=input_data.n_paths,
        seed=input_data.seed,
        model_active=input_data.model_active,  # type: ignore[arg-type]
        model_technical=input_data.model_technical,  # type: ignore[arg-type]
        retired_interest_rate=input_data.retired_interest_rate,
        contribution_multiplier=input_data.contribution_multiplier,
        valuation_terminal_age=input_data.valuation_terminal_age,
        target_funding_ratio=input_data.target_funding_ratio,
        annual_asset_return=input_data.stochastic_asset_return,
        salary_growth_rate=input_data.salary_growth_rate,
        turnover_rate=input_data.turnover_rate,
        entry_assumptions=EntryAssumptions(
            entry_count_per_year=input_data.entry_count_per_year
        ),
        output_dir=Path(input_data.output_dir) / "stochastic_sidecar",
    )
    return result.funding_ratio_summary.copy(deep=True)


def _build_goal1_kpi_summary(
    funding_ratio: pd.DataFrame,
    annual_cashflows: pd.DataFrame,
    valuation: pd.DataFrame,
    cashflows: pd.DataFrame,
    stochastic_summary: pd.DataFrame | None,
) -> pd.DataFrame:
    initial_fr = float(funding_ratio.iloc[0]["funding_ratio_percent"])
    final_fr = float(funding_ratio.iloc[-1]["funding_ratio_percent"])
    min_fr = float(funding_ratio["funding_ratio_percent"].min())
    current_net = 0.0 if annual_cashflows.empty else float(annual_cashflows.iloc[0]["net_cashflow"])
    inflection = find_liquidity_inflection_year(annual_cashflows, use_structural=True)
    income_yield = _income_yield(cashflows, float(funding_ratio.iloc[0]["asset_value"]))
    pension_loss = float(valuation.iloc[-1]["pensionierungsverlust"])
    underfunding = (
        None
        if stochastic_summary is None or stochastic_summary.empty
        else float(stochastic_summary.iloc[0].get("P_underfunding", 0.0))
    )
    return pd.DataFrame(
        [
            {
                "current_funding_ratio_percent": initial_fr,
                "final_funding_ratio_percent": final_fr,
                "minimum_funding_ratio_percent": min_fr,
                "net_cashflow_current_year": current_net,
                "liquidity_inflection_year": inflection,
                "income_yield": income_yield,
                "pensionierungsverlust": pension_loss,
                "underfunding_probability": underfunding,
            }
        ]
    )


def _income_yield(cashflows: pd.DataFrame, opening_assets: float) -> float:
    """First-year IP/DV income divided by opening assets (annual yield)."""
    if opening_assets <= 0 or cashflows.empty:
        return 0.0
    income_events = cashflows.loc[cashflows["type"].isin(["IP", "DV"])]
    if income_events.empty:
        return 0.0
    first_year = int(pd.to_datetime(income_events["time"]).dt.year.min())
    first_year_mask = pd.to_datetime(income_events["time"]).dt.year == first_year
    annual_income = float(income_events.loc[first_year_mask, "payoff"].sum())
    return annual_income / opening_assets


def _build_validation_checks(
    *,
    allocation_table: pd.DataFrame,
    funding_ratio: pd.DataFrame,
    kpi_summary: pd.DataFrame,
    valuation_snapshots: pd.DataFrame,
    initial_state: BVGPortfolioState,
) -> pd.DataFrame:
    """Plausibility checks against Swiss PK sector benchmarks (Complementa 2024)."""
    allocations = _allocation_weights(allocation_table)
    members = max(1, initial_state.member_count_total)
    retired_count = initial_state.retired_count_total
    rentnerquote = retired_count / members if members > 0 else 0.0

    initial_fr = float(funding_ratio.iloc[0]["funding_ratio_percent"])
    final_fr = float(funding_ratio.iloc[-1]["funding_ratio_percent"])
    min_fr = float(funding_ratio["funding_ratio_percent"].min())
    fr_swing = final_fr - initial_fr

    initial_liability = float(valuation_snapshots.iloc[0]["total_stage2b_liability"])
    pension_loss_terminal = float(valuation_snapshots.iloc[-1]["pensionierungsverlust"])
    pension_loss_ratio = (
        abs(pension_loss_terminal) / initial_liability if initial_liability > 0 else 0.0
    )

    bond_weight = allocations.get("bonds", 0.0)
    equity_weight = allocations.get("equities", 0.0)

    rows = [
        _check_row(
            "FR initial >= 100% (BVG legal floor)",
            initial_fr,
            ">= 100",
            initial_fr >= 100.0,
        ),
        _check_row(
            "FR minimum >= 90% (sustainability)",
            min_fr,
            ">= 90",
            min_fr >= 90.0,
        ),
        _check_row(
            "FR trajectory swing within +/-30pp",
            fr_swing,
            "-30 to +30 pp vs initial",
            -30.0 <= fr_swing <= 30.0,
        ),
        _check_row(
            "Allocation weights sum to 1.0",
            sum(allocations.values()),
            "= 1.0 +/- 1e-6",
            math.isclose(sum(allocations.values()), 1.0, abs_tol=1e-6),
        ),
        _check_row(
            "Bond weight 20-50% (Complementa norm 30.9%)",
            bond_weight,
            "0.20 to 0.50",
            0.20 <= bond_weight <= 0.50,
        ),
        _check_row(
            "Equity weight 15-40% (Complementa norm 28%)",
            equity_weight,
            "0.15 to 0.40",
            0.15 <= equity_weight <= 0.40,
        ),
        _check_row(
            "Rentnerquote 10-30% (Complementa norm 15-22%)",
            rentnerquote,
            "0.10 to 0.30",
            0.10 <= rentnerquote <= 0.30,
        ),
        _check_row(
            "Liability gap / liability < 15% (terminal)",
            pension_loss_ratio,
            "< 0.15",
            pension_loss_ratio < 0.15,
        ),
        _check_row(
            "Income yield 1-5% (Complementa 20Y avg 3.7%)",
            float(kpi_summary.iloc[0]["income_yield"]),
            "0.01 to 0.05",
            0.01 <= float(kpi_summary.iloc[0]["income_yield"]) <= 0.05,
        ),
    ]
    return pd.DataFrame(rows)


def _check_row(metric: str, value: float, benchmark: str, passed: bool) -> dict[str, object]:
    return {"metric": metric, "value": value, "benchmark": benchmark, "passed": bool(passed)}


def _write_goal1_csv_outputs(output_dir: Path, outputs: dict[str, pd.DataFrame]) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for filename, df in outputs.items():
        paths[filename.removesuffix(".csv")] = _write_csv(df, output_dir / filename)
    return paths


def _write_csv(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


def _write_goal1_plots(
    output_dir: Path,
    *,
    funding_ratio: pd.DataFrame,
    net_cashflow: pd.DataFrame,
    cashflow_by_source: pd.DataFrame,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    figures = {
        "funding_ratio_trajectory": _plot_funding_ratio(funding_ratio),
        "net_cashflow": _plot_net_cashflow(net_cashflow),
        "cashflow_by_source": _plot_cashflow_by_source(cashflow_by_source),
        "assets_vs_liabilities": _plot_assets_vs_liabilities(funding_ratio),
    }
    paths: dict[str, Path] = {}
    for key, fig in figures.items():
        path = output_dir / f"{key}.png"
        fig.savefig(path, format="png", bbox_inches="tight")
        plt.close(fig)
        paths[key] = path
    return paths


def _build_cashflow_by_source_table(cashflows: pd.DataFrame) -> pd.DataFrame:
    if cashflows.empty:
        return pd.DataFrame(columns=["reporting_year", "source", "total_payoff"])
    work = cashflows.copy(deep=True)
    work["reporting_year"] = pd.to_datetime(work["time"]).dt.year.astype(int)
    return (
        work.groupby(["reporting_year", "source"], as_index=False)["payoff"]
        .sum()
        .rename(columns={"payoff": "total_payoff"})
        [["reporting_year", "source", "total_payoff"]]
    )


def _plot_funding_ratio(funding_ratio: pd.DataFrame):
    fig, ax = plt.subplots()
    df = funding_ratio.sort_values("projection_year")
    ax.plot(df["projection_year"], df["funding_ratio_percent"], marker="o")
    ax.set_title("Funding Ratio")
    ax.set_xlabel("Projection year")
    ax.set_ylabel("Funding ratio (%)")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


def _plot_net_cashflow(net_cashflow: pd.DataFrame):
    fig, ax = plt.subplots()
    if not net_cashflow.empty:
        df = net_cashflow.sort_values("reporting_year")
        ax.plot(df["reporting_year"], df["net_cashflow"], marker="o", label="Net")
        ax.plot(
            df["reporting_year"],
            df["structural_net_cashflow"],
            marker="o",
            label="Structural",
        )
        ax.legend()
    ax.set_title("Net Cashflow")
    ax.set_xlabel("Reporting year")
    ax.set_ylabel("Cashflow")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


def _plot_cashflow_by_source(cashflow_by_source: pd.DataFrame):
    fig, ax = plt.subplots()
    if not cashflow_by_source.empty:
        pivot = cashflow_by_source.pivot(
            index="reporting_year",
            columns="source",
            values="total_payoff",
        ).fillna(0.0)
        pivot.plot(ax=ax, marker="o")
    ax.set_title("Cashflow by Source")
    ax.set_xlabel("Reporting year")
    ax.set_ylabel("Total payoff")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


def _plot_assets_vs_liabilities(funding_ratio: pd.DataFrame):
    fig, ax = plt.subplots()
    df = funding_ratio.sort_values("projection_year")
    ax.plot(df["projection_year"], df["asset_value"], marker="o", label="Assets")
    ax.plot(
        df["projection_year"],
        df["total_stage1_liability"],
        marker="o",
        label="Liabilities",
    )
    ax.set_title("Assets vs Liabilities")
    ax.set_xlabel("Projection year")
    ax.set_ylabel("Value")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    return fig


def _comparison_row(stage: str, adds: str, csv_outputs: dict[str, pd.DataFrame]) -> dict[str, object]:
    funding = _find_csv(csv_outputs, "funding_ratio")
    annual = _find_csv(csv_outputs, "annual_cashflows")
    return {
        "stage": stage,
        "adds": adds,
        "status": "ok",
        "initial_funding_ratio_percent": _funding_value(funding, "first"),
        "final_funding_ratio_percent": _funding_value(funding, "last"),
        "minimum_funding_ratio_percent": None if funding is None else float(funding["funding_ratio_percent"].min()) if "funding_ratio_percent" in funding else None,
        "first_year_net_cashflow": None if annual is None or annual.empty else float(annual.iloc[0]["net_cashflow"]),
        "error": "",
    }


def _comparison_error_row(stage: str, adds: str, exc: Exception) -> dict[str, object]:
    return {
        "stage": stage,
        "adds": adds,
        "status": "error",
        "initial_funding_ratio_percent": None,
        "final_funding_ratio_percent": None,
        "minimum_funding_ratio_percent": None,
        "first_year_net_cashflow": None,
        "error": str(exc),
    }


def _find_csv(csv_outputs: dict[str, pd.DataFrame], pattern: str) -> pd.DataFrame | None:
    for name, df in csv_outputs.items():
        if pattern in name:
            return df
    return None


def _funding_value(df: pd.DataFrame | None, position: str) -> float | None:
    if df is None or df.empty:
        return None
    if "funding_ratio_percent" not in df.columns:
        return None
    row = df.iloc[0] if position == "first" else df.iloc[-1]
    return float(row["funding_ratio_percent"])


def _allocation_weights(df: pd.DataFrame) -> dict[str, float]:
    table = _validate_columns(df, ALLOCATION_COLUMNS, "allocation_table")
    weights: dict[str, float] = {}
    for _, row in table.iterrows():
        asset_class = str(row["asset_class"]).strip().lower()
        if not asset_class:
            raise ValueError("asset_class must be non-empty")
        weight = _validate_real(row["weight"], "weight", min_value=0.0)
        weights[asset_class] = weights.get(asset_class, 0.0) + weight
    total = sum(weights.values())
    if total > 1.5:
        weights = {key: value / 100.0 for key, value in weights.items()}
        total = sum(weights.values())
    if not math.isclose(total, 1.0, abs_tol=1e-6):
        raise ValueError(f"allocation weights must sum to 1.0, got {total}")
    return weights


def _stk_contract_config(
    asset_class: str,
    start_year: int,
    nominal: float,
    dividend_yield: float,
    growth: float,
    horizon_years: int = 12,
) -> AALContractConfig:
    years = max(1, int(horizon_years))
    return make_stk_contract_config_from_nominal(
        contract_id=f"COCKPIT_{asset_class.upper()}",
        start_year=start_year,
        divestment_year=start_year + years,
        nominal_value=nominal,
        dividend_yield=dividend_yield,
        market_value_growth=growth,
        price_at_purchase=100.0,
        currency="CHF",
    )


def _retired_origins(states: tuple[BVGPortfolioState, ...]) -> dict[str, tuple[int, int]]:
    origins: dict[str, tuple[int, int]] = {}
    for projection_year, state in enumerate(states):
        for cohort in state.retired_cohorts:
            origins.setdefault(cohort.cohort_id, (projection_year, cohort.age))
    return origins


def _validate_columns(df: pd.DataFrame, columns: tuple[str, ...], name: str) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"{name} must be DataFrame")
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(f"{name} missing required columns: {missing}")
    result = df[list(columns)].copy(deep=True)
    return result.dropna(how="all")


def _validate_int(value: object, name: str, *, min_value: int | None = None) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if isinstance(value, numbers.Integral):
        result = int(value)
    elif isinstance(value, numbers.Real) and float(value).is_integer():
        result = int(value)
    else:
        raise TypeError(f"{name} must be integer-like")
    if min_value is not None and result < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {result}")
    return result


def _validate_real(
    value: object,
    name: str,
    *,
    min_value: float | None = None,
    strict: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be numeric")
    result = float(value)
    if math.isnan(result):
        raise ValueError(f"{name} must not be NaN")
    if min_value is not None:
        if strict and result <= min_value:
            raise ValueError(f"{name} must be > {min_value}, got {result}")
        if not strict and result < min_value:
            raise ValueError(f"{name} must be >= {min_value}, got {result}")
    return result


def _reject_protected_output_dir(output_dir: str | Path) -> None:
    resolved = Path(output_dir).resolve(strict=False)
    for protected in PROTECTED_OUTPUT_DIRS:
        protected_resolved = protected.resolve(strict=False)
        try:
            resolved.relative_to(protected_resolved)
        except ValueError:
            continue
        raise ValueError(f"Goal-1 workflow must not target {protected}")
