import math

import pandas as pd
import pytest

from pk_alm.bvg_liability_engine.domain_models.cohorts import ActiveCohort
from pk_alm.bvg_liability_engine.population_dynamics.entry_dynamics import (
    EntryAssumptions,
    apply_entries_to_portfolio,
    build_entry_cashflow_record,
    generate_entry_cohort_for_year,
    get_default_entry_assumptions,
)
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState


def test_entry_assumptions_defaults_validate() -> None:
    assumptions = get_default_entry_assumptions()
    assert isinstance(assumptions, EntryAssumptions)
    assert assumptions.entry_count_per_year == 1
    assert assumptions.entry_capital_per_person == 0.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"entry_age": True},
        {"entry_age": -1},
        {"entry_count_per_year": True},
        {"entry_count_per_year": -1},
        {"entry_gross_salary": True},
        {"entry_gross_salary": math.nan},
        {"entry_gross_salary": -1.0},
        {"entry_capital_per_person": True},
        {"entry_capital_per_person": math.nan},
        {"entry_capital_per_person": -1.0},
        {"cohort_id_prefix": " "},
    ],
)
def test_entry_assumptions_reject_invalid_values(kwargs: dict[str, object]) -> None:
    with pytest.raises((TypeError, ValueError)):
        EntryAssumptions(**kwargs)


def test_zero_entry_count_returns_none_and_noop() -> None:
    assumptions = EntryAssumptions(entry_count_per_year=0)
    portfolio = BVGPortfolioState()
    assert generate_entry_cohort_for_year(assumptions, 2026) is None
    new_portfolio, records = apply_entries_to_portfolio(
        portfolio, assumptions, 2026, pd.Timestamp("2026-12-31")
    )
    assert new_portfolio == portfolio
    assert records == ()


def test_generate_entry_cohort_for_year_uses_approved_id_scheme() -> None:
    assumptions = EntryAssumptions(
        entry_age=30,
        entry_count_per_year=4,
        entry_gross_salary=70_000.0,
        entry_capital_per_person=10_000.0,
    )
    cohort = generate_entry_cohort_for_year(assumptions, 2027, nonce="A")
    assert cohort == ActiveCohort("ENTRY_2027_A", 30, 4, 70_000.0, 10_000.0)


def test_build_entry_cashflow_record_suppresses_zero_capital() -> None:
    cohort = ActiveCohort("ENTRY_2026_0", 25, 3, 65_000.0, 0.0)
    assert build_entry_cashflow_record(cohort, "2026-12-31") is None


def test_build_entry_cashflow_record_positive_inflow() -> None:
    cohort = ActiveCohort("ENTRY_2026_0", 25, 3, 65_000.0, 10_000.0)
    record = build_entry_cashflow_record(cohort, "2026-12-31")
    assert record is not None
    assert record.type == "IN"
    assert record.source == "BVG"
    assert record.payoff == pytest.approx(30_000.0)
    assert record.nominalValue == pytest.approx(30_000.0)


def test_apply_entries_appends_cohort_and_returns_in_record() -> None:
    portfolio = BVGPortfolioState(
        active_cohorts=(ActiveCohort("ACT", 40, 2, 80_000.0, 100_000.0),)
    )
    assumptions = EntryAssumptions(
        entry_count_per_year=2,
        entry_capital_per_person=5_000.0,
    )
    new_portfolio, records = apply_entries_to_portfolio(
        portfolio, assumptions, 2026, "2026-12-31"
    )
    assert new_portfolio.projection_year == portfolio.projection_year
    assert [c.cohort_id for c in new_portfolio.active_cohorts] == [
        "ACT",
        "ENTRY_2026_0",
    ]
    assert len(records) == 1
    assert records[0].payoff == pytest.approx(10_000.0)
