"""Tests for AAL simulation settings and event cut-off filters."""

import pandas as pd
import pytest

from pk_alm.actus_asset_engine.filters import filter_cashflows_for_settings
from pk_alm.actus_asset_engine.simulation_settings import AALSimulationSettings
from pk_alm.cashflows.schema import CASHFLOW_COLUMNS


def _cashflows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "contractId": "BOND",
                "time": pd.Timestamp("2021-01-01"),
                "type": "IED",
                "payoff": -100_000.0,
                "nominalValue": 100_000.0,
                "currency": "CHF",
                "source": "ACTUS",
            },
            {
                "contractId": "BOND",
                "time": pd.Timestamp("2026-12-31"),
                "type": "IP",
                "payoff": 1_500.0,
                "nominalValue": 100_000.0,
                "currency": "CHF",
                "source": "ACTUS",
            },
            {
                "contractId": "BOND",
                "time": pd.Timestamp("2030-12-31"),
                "type": "MD",
                "payoff": 100_000.0,
                "nominalValue": 0.0,
                "currency": "CHF",
                "source": "ACTUS",
            },
        ],
        columns=list(CASHFLOW_COLUMNS),
    )


def test_settings_default_event_start_equals_analysis_date():
    settings = AALSimulationSettings(
        analysis_date="2026-01-01T00:00:00",
        event_end_date="2030-12-31T00:00:00",
    )

    assert settings.event_start_date == pd.Timestamp("2026-01-01")
    assert settings.cashflow_cutoff_mode == "from_status_date"
    assert settings.mode == "validated"


def test_settings_reject_invalid_end_before_start():
    with pytest.raises(ValueError, match="event_end_date"):
        AALSimulationSettings(
            analysis_date="2026-01-01",
            event_start_date="2026-01-01",
            event_end_date="2025-12-31",
        )


def test_from_status_date_filters_historical_events():
    settings = AALSimulationSettings(
        analysis_date="2026-01-01",
        event_start_date="2026-01-01",
        event_end_date="2026-12-31",
    )

    result = filter_cashflows_for_settings(_cashflows(), settings)

    assert result["type"].tolist() == ["IP"]


def test_all_events_keeps_history_but_applies_end_date():
    settings = AALSimulationSettings(
        analysis_date="2026-01-01",
        event_start_date="2026-01-01",
        event_end_date="2026-12-31",
        cashflow_cutoff_mode="all_events",
    )

    result = filter_cashflows_for_settings(_cashflows(), settings)

    assert result["type"].tolist() == ["IED", "IP"]
