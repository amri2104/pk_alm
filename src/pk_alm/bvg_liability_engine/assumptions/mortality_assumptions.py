"""Mortality assumption container.

Wraps the EK 0105 educational tables loaded from
:mod:`pk_alm.bvg_liability_engine.actuarial_data.mortality_tables`. Engine
code branches on ``mode``: when ``"off"``, no mortality decrement is applied
(certain-annuity sight); when ``"ek0105"``, the configured table drives
survival.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pk_alm.bvg_liability_engine.actuarial_assumptions.mortality import (
    DEFAULT_EK0105_TABLE_ID,
    MORTALITY_MODE_EK0105,
    MORTALITY_MODE_OFF,
    MORTALITY_SOURCE_CAVEAT,
    SUPPORTED_EK0105_TABLE_IDS,
    MortalityTable,
    load_ek0105_table,
)

MortalityMode = Literal["off", "ek0105"]


@dataclass(frozen=True)
class MortalityAssumptions:
    """Frozen assumption container for mortality.

    Attributes:
        mode: ``"off"`` disables mortality (certain-annuity); ``"ek0105"``
            applies the configured EK 0105 table.
        table_id: One of :data:`SUPPORTED_EK0105_TABLE_IDS` (used when
            ``mode == "ek0105"``).
        source_caveat: Free-text caveat describing the table source. Default
            references EK 0105's educational status.
    """

    mode: MortalityMode = MORTALITY_MODE_OFF
    table_id: str = DEFAULT_EK0105_TABLE_ID
    source_caveat: str = MORTALITY_SOURCE_CAVEAT

    def __post_init__(self) -> None:
        if self.mode not in (MORTALITY_MODE_OFF, MORTALITY_MODE_EK0105):
            raise ValueError(
                f"mode must be 'off' or 'ek0105', got {self.mode!r}"
            )
        if self.table_id not in SUPPORTED_EK0105_TABLE_IDS:
            raise ValueError(
                f"table_id must be one of {SUPPORTED_EK0105_TABLE_IDS}, "
                f"got {self.table_id!r}"
            )
        if not isinstance(self.source_caveat, str):
            raise TypeError("source_caveat must be a string")

    def is_active(self) -> bool:
        return self.mode == MORTALITY_MODE_EK0105

    def load_table(self) -> MortalityTable | None:
        """Load the configured EK 0105 table, or ``None`` if mortality is off."""
        if not self.is_active():
            return None
        return load_ek0105_table(self.table_id)
