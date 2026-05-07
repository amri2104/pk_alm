"""Stage-2D parity by summary statistics.

The legacy stochastic engine and the new ``stochastic_runner`` should give
identical aggregate distributions when fed the same pre-generated active
rate-path array — i.e. same per-year mean cashflow, same per-year
percentile band, same final-state moments.

This test does NOT require byte-for-byte cashflow equality (path-order may
shift if internal RNG call order changes). It does require the realized
cashflow distribution to match exactly, since both engines deterministically
project the BVG mechanics given the same rate path.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from pk_alm.bvg_liability_engine.assumptions import (
    BVGAssumptions,
    EntryAssumptions,
    FlatRateCurve,
    MortalityAssumptions,
)
from pk_alm.bvg_liability_engine.domain_models.cohorts import (
    ActiveCohort,
    RetiredCohort,
)
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.bvg_liability_engine.orchestration.legacy.engine_stage2d import (
    run_bvg_engine_stage2d,
)
from pk_alm.bvg_liability_engine.orchestration.stochastic_runner import (
    run_stochastic_bvg_engine,
)
from pk_alm.bvg_liability_engine.population_dynamics.entry_policies import (
    FixedEntryPolicy,
)


def _portfolio() -> BVGPortfolioState:
    return BVGPortfolioState(
        active_cohorts=(
            ActiveCohort(
                cohort_id="ACT_30",
                age=30,
                count=8,
                gross_salary_per_person=70_000.0,
                capital_active_per_person=50_000.0,
            ),
            ActiveCohort(
                cohort_id="ACT_50",
                age=50,
                count=4,
                gross_salary_per_person=95_000.0,
                capital_active_per_person=400_000.0,
            ),
        ),
        retired_cohorts=(
            RetiredCohort(
                cohort_id="RET_72",
                age=72,
                count=6,
                annual_pension_per_person=28_000.0,
                capital_rente_per_person=420_000.0,
            ),
        ),
    )


def _make_paths(n_paths: int, horizon: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return 0.0125 + 0.005 * rng.standard_normal((n_paths, horizon))


def test_stochastic_runner_path_aggregates_match_legacy_stage2d() -> None:
    initial = _portfolio()
    horizon = 8
    n_paths = 25
    rate_paths = _make_paths(n_paths, horizon, seed=7)
    entry = EntryAssumptions(entry_count_per_year=1)

    legacy = run_bvg_engine_stage2d(
        initial_state=initial,
        horizon_years=horizon,
        rate_paths_active=rate_paths,
        retired_interest_rate=0.0176,
        salary_growth_rate=0.015,
        turnover_rate=0.02,
        entry_assumptions=entry,
        contribution_multiplier=1.4,
        start_year=2026,
        retirement_age=65,
        capital_withdrawal_fraction=0.35,
        conversion_rate=0.068,
    )

    assumptions = BVGAssumptions(
        start_year=2026,
        horizon_years=horizon,
        retirement_age=65,
        valuation_terminal_age=90,
        active_crediting_rate=FlatRateCurve(0.0125),  # overridden per path
        retired_interest_rate=FlatRateCurve(0.0176),
        technical_discount_rate=FlatRateCurve(0.0176),
        economic_discount_rate=FlatRateCurve(0.0176),
        salary_growth_rate=FlatRateCurve(0.015),
        conversion_rate=FlatRateCurve(0.068),
        turnover_rate=0.02,
        capital_withdrawal_fraction=0.35,
        contribution_multiplier=1.4,
        mortality=MortalityAssumptions(mode="off"),
        entry_policy=FixedEntryPolicy(entry),
    )
    new = run_stochastic_bvg_engine(
        initial_state=initial,
        assumptions=assumptions,
        rate_paths_active=rate_paths,
    )

    # Compare net cashflow per path by summing payoffs.
    legacy_totals = np.array(
        [pr.cashflows["payoff"].sum() for pr in legacy.path_results]
    )
    new_totals = np.array(
        [pr.cashflows["payoff"].sum() for pr in new.path_results]
    )
    np.testing.assert_allclose(
        np.sort(new_totals), np.sort(legacy_totals), rtol=1e-9, atol=1e-9
    )

    # Compare final-state total capital across paths (sorted; same values).
    legacy_final_total_cap = np.array(
        [pr.portfolio_states[-1].total_capital for pr in legacy.path_results]
    )
    new_final_total_cap = np.array(
        [pr.portfolio_states[-1].total_capital for pr in new.path_results]
    )
    np.testing.assert_allclose(
        np.sort(new_final_total_cap),
        np.sort(legacy_final_total_cap),
        rtol=1e-9,
        atol=1e-9,
    )

    # Path order should also match because rate_paths feed both engines in
    # the same row order; check unsorted equality.
    np.testing.assert_allclose(new_totals, legacy_totals, rtol=1e-9, atol=1e-9)


def test_stochastic_runner_per_year_payoff_distribution_matches_legacy() -> None:
    initial = _portfolio()
    horizon = 6
    n_paths = 15
    rate_paths = _make_paths(n_paths, horizon, seed=11)
    entry = EntryAssumptions(entry_count_per_year=1)

    legacy = run_bvg_engine_stage2d(
        initial_state=initial,
        horizon_years=horizon,
        rate_paths_active=rate_paths,
        retired_interest_rate=0.0176,
        entry_assumptions=entry,
    )

    assumptions = BVGAssumptions(
        start_year=2026,
        horizon_years=horizon,
        retirement_age=65,
        valuation_terminal_age=90,
        active_crediting_rate=FlatRateCurve(0.0125),
        retired_interest_rate=FlatRateCurve(0.0176),
        technical_discount_rate=FlatRateCurve(0.0176),
        economic_discount_rate=FlatRateCurve(0.0176),
        salary_growth_rate=FlatRateCurve(0.015),
        conversion_rate=FlatRateCurve(0.068),
        turnover_rate=0.02,
        capital_withdrawal_fraction=0.35,
        contribution_multiplier=1.4,
        mortality=MortalityAssumptions(mode="off"),
        entry_policy=FixedEntryPolicy(entry),
    )
    new = run_stochastic_bvg_engine(
        initial_state=initial,
        assumptions=assumptions,
        rate_paths_active=rate_paths,
    )

    # Per-year aggregated payoff (sum across all flow types) must match.
    for path_idx in range(n_paths):
        legacy_df = legacy.path_results[path_idx].cashflows.copy()
        new_df = new.path_results[path_idx].cashflows.copy()
        legacy_df["year"] = pd.to_datetime(legacy_df["time"]).dt.year
        new_df["year"] = pd.to_datetime(new_df["time"]).dt.year
        legacy_grp = legacy_df.groupby("year")["payoff"].sum().sort_index()
        new_grp = new_df.groupby("year")["payoff"].sum().sort_index()
        pd.testing.assert_series_equal(
            new_grp, legacy_grp, check_dtype=False, check_names=False
        )
