"""Simulation settings for forward-looking ACTUS/AAL cashflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

AALMode = Literal["validated", "exploratory"]
CashflowCutoffMode = Literal["from_status_date", "all_events"]


def _parse_timestamp(value: object, name: str) -> pd.Timestamp:
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} could not be parsed as a timestamp") from exc
    if pd.isna(timestamp):
        raise ValueError(f"{name} must not be NaT/None/NaN")
    return timestamp


@dataclass(frozen=True)
class AALSimulationSettings:
    """Simulation cut-off and mode settings for the AAL asset engine."""

    analysis_date: object
    event_start_date: object | None = None
    event_end_date: object | None = None
    mode: AALMode = "validated"
    cashflow_cutoff_mode: CashflowCutoffMode = "from_status_date"

    def __post_init__(self) -> None:
        analysis_date = _parse_timestamp(self.analysis_date, "analysis_date")
        event_start_date = (
            analysis_date
            if self.event_start_date is None
            else _parse_timestamp(self.event_start_date, "event_start_date")
        )
        event_end_date = (
            pd.Timestamp.max.normalize()
            if self.event_end_date is None
            else _parse_timestamp(self.event_end_date, "event_end_date")
        )
        if event_end_date < event_start_date:
            raise ValueError("event_end_date must be >= event_start_date")
        if self.mode not in ("validated", "exploratory"):
            raise ValueError("mode must be 'validated' or 'exploratory'")
        if self.cashflow_cutoff_mode not in ("from_status_date", "all_events"):
            raise ValueError(
                "cashflow_cutoff_mode must be 'from_status_date' or 'all_events'"
            )

        object.__setattr__(self, "analysis_date", analysis_date)
        object.__setattr__(self, "event_start_date", event_start_date)
        object.__setattr__(self, "event_end_date", event_end_date)


def default_aal_simulation_settings() -> AALSimulationSettings:
    """Return the default thesis ALM cut-off window."""
    return AALSimulationSettings(
        analysis_date="2026-01-01T00:00:00",
        event_start_date="2026-01-01T00:00:00",
        event_end_date="2038-12-31T00:00:00",
        mode="validated",
        cashflow_cutoff_mode="from_status_date",
    )
