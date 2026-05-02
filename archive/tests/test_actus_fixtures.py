import math

import pandas as pd
import pytest

from pk_alm.adapters.actus_adapter import (
    ACTUS_SOURCE,
    actus_events_to_cashflow_dataframe,
    actus_events_to_cashflow_records,
)
from pk_alm.adapters.actus_fixtures import (
    build_fixed_rate_bond_cashflow_dataframe,
    build_fixed_rate_bond_events,
)
from pk_alm.analytics.cashflows import summarize_cashflows_by_year
from pk_alm.cashflows.schema import CASHFLOW_COLUMNS, validate_cashflow_dataframe
from pk_alm.scenarios.stage1_baseline import run_stage1_baseline


def _standard_events(**overrides):
    kwargs = dict(
        contract_id="BOND_1",
        start_year=2026,
        maturity_year=2028,
        nominal_value=100000.0,
        annual_coupon_rate=0.02,
    )
    kwargs.update(overrides)
    return build_fixed_rate_bond_events(**kwargs)


def _event_summary(events):
    return [
        (
            event["event_date"],
            event["event_type"],
            event["payoff"],
            event["nominal_value"],
            event["currency"],
        )
        for event in events
    ]


# ---------------------------------------------------------------------------
# A. Standard fixed-rate bond events
# ---------------------------------------------------------------------------


def test_standard_fixed_rate_bond_events():
    events = _standard_events()

    assert len(events) == 3
    assert _event_summary(events) == [
        ("2027-12-31", "IP", pytest.approx(2000.0), 100000.0, "CHF"),
        ("2028-12-31", "IP", pytest.approx(2000.0), 100000.0, "CHF"),
        ("2028-12-31", "MD", pytest.approx(100000.0), 100000.0, "CHF"),
    ]
    assert [event["contract_id"] for event in events] == ["BOND_1"] * 3
    assert [event["event_type"] for event in events[-2:]] == ["IP", "MD"]
    assert all(
        list(event.keys())
        == [
            "contract_id",
            "event_date",
            "event_type",
            "payoff",
            "nominal_value",
            "currency",
        ]
        for event in events
    )


# ---------------------------------------------------------------------------
# B. Purchase event option
# ---------------------------------------------------------------------------


def test_purchase_event_option_adds_initial_ied_outflow():
    events = _standard_events(include_purchase_event=True)

    assert len(events) == 4
    assert events[0] == {
        "contract_id": "BOND_1",
        "event_date": "2026-01-01",
        "event_type": "IED",
        "payoff": -100000.0,
        "nominal_value": 100000.0,
        "currency": "CHF",
    }
    assert _event_summary(events[1:]) == _event_summary(_standard_events())


# ---------------------------------------------------------------------------
# C. Zero coupon bond
# ---------------------------------------------------------------------------


def test_zero_coupon_bond_still_emits_coupon_events():
    events = _standard_events(annual_coupon_rate=0.0)

    assert len(events) == 3
    assert [event["event_type"] for event in events] == ["IP", "IP", "MD"]
    assert [event["payoff"] for event in events] == pytest.approx(
        [0.0, 0.0, 100000.0]
    )


# ---------------------------------------------------------------------------
# D. Multi-year order
# ---------------------------------------------------------------------------


def test_multi_year_order_and_final_year_sequence():
    events = build_fixed_rate_bond_events(
        contract_id="BOND_LONG",
        start_year=2026,
        maturity_year=2030,
        nominal_value=100000.0,
        annual_coupon_rate=0.03,
    )

    years = [int(str(event["event_date"])[:4]) for event in events]
    assert years == sorted(years)

    non_final = [event for event in events if event["event_date"] != "2030-12-31"]
    assert [event["event_type"] for event in non_final] == ["IP", "IP", "IP"]
    assert [event["event_date"] for event in non_final] == [
        "2027-12-31",
        "2028-12-31",
        "2029-12-31",
    ]

    final = [event for event in events if event["event_date"] == "2030-12-31"]
    assert [event["event_type"] for event in final] == ["IP", "MD"]
    assert [event["payoff"] for event in final] == pytest.approx(
        [3000.0, 100000.0]
    )


# ---------------------------------------------------------------------------
# E. DataFrame helper
# ---------------------------------------------------------------------------


def test_cashflow_dataframe_helper_returns_schema_valid_actus_dataframe():
    df = build_fixed_rate_bond_cashflow_dataframe(
        contract_id="BOND_1",
        start_year=2026,
        maturity_year=2028,
        nominal_value=100000.0,
        annual_coupon_rate=0.02,
        include_purchase_event=True,
    )

    assert list(df.columns) == list(CASHFLOW_COLUMNS)
    assert df.shape == (4, len(CASHFLOW_COLUMNS))
    assert (df["source"] == ACTUS_SOURCE).all()
    assert validate_cashflow_dataframe(df) is True


# ---------------------------------------------------------------------------
# F. Adapter integration
# ---------------------------------------------------------------------------


def test_adapter_integration_preserves_order_through_records_and_dataframe():
    events = _standard_events(include_purchase_event=True)

    records = actus_events_to_cashflow_records(events)
    df = actus_events_to_cashflow_dataframe(events)

    assert [record.type for record in records] == ["IED", "IP", "IP", "MD"]
    assert list(df["type"]) == ["IED", "IP", "IP", "MD"]
    assert list(df["time"]) == [
        pd.Timestamp("2026-01-01"),
        pd.Timestamp("2027-12-31"),
        pd.Timestamp("2028-12-31"),
        pd.Timestamp("2028-12-31"),
    ]
    assert validate_cashflow_dataframe(df) is True
    assert all(record.source == ACTUS_SOURCE for record in records)


# ---------------------------------------------------------------------------
# G. Annual cashflow analytics integration
# ---------------------------------------------------------------------------


def test_annual_cashflow_analytics_places_bond_events_in_other_cashflow():
    df = build_fixed_rate_bond_cashflow_dataframe(
        contract_id="BOND_1",
        start_year=2026,
        maturity_year=2028,
        nominal_value=100000.0,
        annual_coupon_rate=0.02,
        include_purchase_event=True,
    )

    annual = summarize_cashflows_by_year(df)

    assert list(annual["reporting_year"]) == [2026, 2027, 2028]
    assert list(annual["other_cashflow"]) == pytest.approx(
        [-100000.0, 2000.0, 102000.0]
    )
    assert list(annual["net_cashflow"]) == pytest.approx(
        [-100000.0, 2000.0, 102000.0]
    )
    assert list(annual["structural_net_cashflow"]) == pytest.approx(
        [0.0, 0.0, 0.0]
    )


# ---------------------------------------------------------------------------
# H. Combine with BVG cashflows
# ---------------------------------------------------------------------------


def test_bond_cashflows_combine_with_bvg_cashflows_for_annual_analytics():
    bvg_result = run_stage1_baseline(horizon_years=1, output_dir=None)
    bvg_df = bvg_result.engine_result.cashflows
    bond_df = build_fixed_rate_bond_cashflow_dataframe(
        contract_id="BOND_1",
        start_year=2026,
        maturity_year=2027,
        nominal_value=100000.0,
        annual_coupon_rate=0.02,
        include_purchase_event=True,
    )

    combined = pd.concat([bvg_df, bond_df], ignore_index=True)
    assert validate_cashflow_dataframe(combined) is True

    bvg_annual = summarize_cashflows_by_year(bvg_df)
    actus_annual = summarize_cashflows_by_year(bond_df)
    combined_annual = summarize_cashflows_by_year(combined)

    bvg_by_year = dict(zip(bvg_annual["reporting_year"], bvg_annual["net_cashflow"]))
    actus_by_year = dict(
        zip(actus_annual["reporting_year"], actus_annual["net_cashflow"])
    )
    combined_by_year = dict(
        zip(combined_annual["reporting_year"], combined_annual["net_cashflow"])
    )
    for year, combined_net in combined_by_year.items():
        expected = float(bvg_by_year.get(year, 0.0)) + float(
            actus_by_year.get(year, 0.0)
        )
        assert combined_net == pytest.approx(expected)

    assert set(combined["source"].unique()) == {"BVG", "ACTUS"}


# ---------------------------------------------------------------------------
# I. Invalid inputs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["", "   ", None, 123])
def test_invalid_contract_id_raises(bad):
    with pytest.raises((TypeError, ValueError)):
        _standard_events(contract_id=bad)


@pytest.mark.parametrize("bad", [True, None, "2026", 1.5, -1])
def test_invalid_start_year_raises(bad):
    with pytest.raises((TypeError, ValueError)):
        _standard_events(start_year=bad)


@pytest.mark.parametrize("maturity_year", [2025, 2026])
def test_maturity_year_must_be_after_start_year(maturity_year):
    with pytest.raises(ValueError):
        _standard_events(start_year=2026, maturity_year=maturity_year)


@pytest.mark.parametrize("bad", [False, None, "2028", 1.5])
def test_invalid_maturity_year_type_raises(bad):
    with pytest.raises(TypeError):
        _standard_events(maturity_year=bad)


@pytest.mark.parametrize("bad", [True, None, "100000", math.nan, 0.0, -1.0])
def test_invalid_nominal_value_raises(bad):
    with pytest.raises((TypeError, ValueError)):
        _standard_events(nominal_value=bad)


@pytest.mark.parametrize("bad", [False, None, "0.02", math.nan, -0.01])
def test_invalid_annual_coupon_rate_raises(bad):
    with pytest.raises((TypeError, ValueError)):
        _standard_events(annual_coupon_rate=bad)


@pytest.mark.parametrize("bad", ["", "   ", None, 123])
def test_invalid_currency_raises(bad):
    with pytest.raises((TypeError, ValueError)):
        _standard_events(currency=bad)


@pytest.mark.parametrize("bad", [None, 0, 1, "True"])
def test_invalid_include_purchase_event_raises(bad):
    with pytest.raises(TypeError):
        _standard_events(include_purchase_event=bad)


# ---------------------------------------------------------------------------
# J. No mutation / deterministic output
# ---------------------------------------------------------------------------


def test_fixed_rate_bond_events_are_deterministic_and_independent():
    first = _standard_events(include_purchase_event=True)
    second = _standard_events(include_purchase_event=True)

    assert first == second
    assert first is not second
    assert first[0] is not second[0]

    first[0]["payoff"] = 0.0

    assert second[0]["payoff"] == pytest.approx(-100000.0)
