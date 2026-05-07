"""Tests for the new BVG assumptions layer (Phase 3)."""

from __future__ import annotations

import math

import pytest

from pk_alm.bvg_liability_engine.assumptions import (
    BVGAssumptions,
    CallableRateCurve,
    EntryAssumptions,
    FlatRateCurve,
    MortalityAssumptions,
    RateCurve,
    StepRateCurve,
)
from pk_alm.bvg_liability_engine.assumptions.rate_curves import (
    expand,
    from_dynamic_parameter,
)
from pk_alm.bvg_liability_engine.population_dynamics.entry_policies import (
    EntryPolicy,
    FixedEntryPolicy,
    NoEntryPolicy,
    ReplacementEntryPolicy,
)


# ---------------------------------------------------------------------------
# RateCurve
# ---------------------------------------------------------------------------


def test_flat_rate_curve_returns_constant() -> None:
    c = FlatRateCurve(0.025)
    assert c.value_at(2026) == 0.025
    assert c.value_at(2050, 7) == 0.025


def test_flat_rate_curve_is_a_rate_curve() -> None:
    assert isinstance(FlatRateCurve(0.0), RateCurve)


def test_flat_rate_curve_rejects_nan() -> None:
    with pytest.raises(ValueError):
        FlatRateCurve(float("nan"))


def test_step_rate_curve_forward_fills() -> None:
    c = StepRateCurve({2026: 0.01, 2028: 0.02})
    assert c.value_at(2025) == 0.01  # before first key clamps to first
    assert c.value_at(2026) == 0.01
    assert c.value_at(2027) == 0.01  # forward-fill
    assert c.value_at(2028) == 0.02
    assert c.value_at(2030) == 0.02


def test_step_rate_curve_rejects_empty() -> None:
    with pytest.raises(ValueError):
        StepRateCurve({})


def test_callable_rate_curve_evaluates_function() -> None:
    c = CallableRateCurve(fn=lambda y, p: 0.001 * (y - 2025) + 0.0001 * p)
    assert math.isclose(c.value_at(2026, 0), 0.001)
    assert math.isclose(c.value_at(2030, 5), 0.005 + 0.0005)


def test_from_dynamic_parameter_scalar_to_flat() -> None:
    c = from_dynamic_parameter(0.018, start_year=2026, horizon_years=12)
    assert isinstance(c, FlatRateCurve)
    assert c.rate == 0.018


def test_from_dynamic_parameter_sequence_to_step() -> None:
    c = from_dynamic_parameter([0.01, 0.02, 0.03], start_year=2026, horizon_years=12)
    assert isinstance(c, StepRateCurve)
    assert c.value_at(2026) == 0.01
    assert c.value_at(2027) == 0.02
    assert c.value_at(2028) == 0.03
    assert c.value_at(2032) == 0.03  # forward-fill


def test_from_dynamic_parameter_rejects_too_long_sequence() -> None:
    with pytest.raises(ValueError):
        from_dynamic_parameter([0.01] * 5, start_year=2026, horizon_years=3)


def test_expand_curve() -> None:
    c = StepRateCurve({2026: 0.01, 2028: 0.02})
    assert expand(c, start_year=2026, horizon_years=4) == (0.01, 0.01, 0.02, 0.02)


# ---------------------------------------------------------------------------
# MortalityAssumptions
# ---------------------------------------------------------------------------


def test_mortality_assumptions_default_off() -> None:
    m = MortalityAssumptions()
    assert m.is_active() is False
    assert m.load_table() is None


def test_mortality_assumptions_ek0105_loads_table() -> None:
    m = MortalityAssumptions(mode="ek0105")
    assert m.is_active() is True
    table = m.load_table()
    assert table is not None
    assert table.table_id == "EKF 0105"


def test_mortality_assumptions_invalid_mode() -> None:
    with pytest.raises(ValueError):
        MortalityAssumptions(mode="bogus")  # type: ignore[arg-type]


def test_mortality_assumptions_invalid_table_id() -> None:
    with pytest.raises(ValueError):
        MortalityAssumptions(mode="ek0105", table_id="ZZZ")


# ---------------------------------------------------------------------------
# Entry policies
# ---------------------------------------------------------------------------


def test_no_entry_policy_returns_empty() -> None:
    p = NoEntryPolicy()
    assert p.entries_for_year(2026, exited_count=5, retired_count=2) == ()


def test_fixed_entry_policy_emits_one_cohort_per_year() -> None:
    p = FixedEntryPolicy(EntryAssumptions(entry_count_per_year=3))
    cohorts = p.entries_for_year(2026, exited_count=0, retired_count=0)
    assert len(cohorts) == 1
    assert cohorts[0].count == 3
    assert cohorts[0].age == 25


def test_fixed_entry_policy_zero_count_emits_nothing() -> None:
    p = FixedEntryPolicy(EntryAssumptions(entry_count_per_year=0))
    assert p.entries_for_year(2026, 0, 0) == ()


def test_replacement_entry_policy_full_replacement() -> None:
    p = ReplacementEntryPolicy(template=EntryAssumptions(), replacement_ratio=1.0)
    cohorts = p.entries_for_year(2026, exited_count=3, retired_count=2)
    assert len(cohorts) == 5
    assert all(c.count == 1 for c in cohorts)
    ids = {c.cohort_id for c in cohorts}
    assert len(ids) == 5  # unique


def test_replacement_entry_policy_partial() -> None:
    p = ReplacementEntryPolicy(template=EntryAssumptions(), replacement_ratio=0.5)
    cohorts = p.entries_for_year(2026, exited_count=3, retired_count=3)
    assert len(cohorts) == 3  # round(0.5 * 6) = 3


def test_replacement_entry_policy_zero_ratio() -> None:
    p = ReplacementEntryPolicy(template=EntryAssumptions(), replacement_ratio=0.0)
    assert p.entries_for_year(2026, 10, 10) == ()


def test_entry_policies_are_entry_policy() -> None:
    assert isinstance(NoEntryPolicy(), EntryPolicy)
    assert isinstance(FixedEntryPolicy(EntryAssumptions()), EntryPolicy)
    assert isinstance(ReplacementEntryPolicy(EntryAssumptions()), EntryPolicy)


# ---------------------------------------------------------------------------
# BVGAssumptions
# ---------------------------------------------------------------------------


def test_bvg_assumptions_defaults() -> None:
    a = BVGAssumptions()
    assert a.start_year == 2026
    assert a.horizon_years == 12
    assert a.retirement_age == 65
    assert a.cashflow_frequency == "annual"
    assert a.periods_per_year == 1
    assert isinstance(a.mortality, MortalityAssumptions)
    assert isinstance(a.entry_policy, NoEntryPolicy)
    assert a.active_crediting_rate.value_at(2026) == 0.0125
    assert a.technical_discount_rate.value_at(2026) == 0.0176
    assert a.economic_discount_rate.value_at(2026) == 0.01


def test_bvg_assumptions_monthly_periods() -> None:
    a = BVGAssumptions(cashflow_frequency="monthly")
    assert a.periods_per_year == 12


def test_bvg_assumptions_rejects_bad_terminal_age() -> None:
    with pytest.raises(ValueError):
        BVGAssumptions(retirement_age=70, valuation_terminal_age=65)


def test_bvg_assumptions_accepts_step_rate_curves() -> None:
    a = BVGAssumptions(
        active_crediting_rate=StepRateCurve({2026: 0.01, 2028: 0.02}),
    )
    assert a.active_crediting_rate.value_at(2030) == 0.02


def test_bvg_assumptions_accepts_replacement_policy() -> None:
    a = BVGAssumptions(
        entry_policy=ReplacementEntryPolicy(
            template=EntryAssumptions(), replacement_ratio=0.5
        ),
    )
    assert isinstance(a.entry_policy, ReplacementEntryPolicy)


def test_bvg_assumptions_rejects_non_curve_rate() -> None:
    with pytest.raises(TypeError):
        BVGAssumptions(active_crediting_rate=0.01)  # type: ignore[arg-type]


def test_bvg_assumptions_rejects_invalid_cashflow_frequency() -> None:
    with pytest.raises(ValueError):
        BVGAssumptions(cashflow_frequency="weekly")  # type: ignore[arg-type]
