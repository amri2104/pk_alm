"""Mortality-table loaders.

Currently delegates to the legacy :mod:`actuarial_assumptions.mortality`
module. Once the refactor reaches Phase 7, the CSVs and primary loader will
move into this package.
"""

from pk_alm.bvg_liability_engine.actuarial_assumptions.mortality import (
    DEFAULT_EK0105_TABLE_ID,
    EKF_0105,
    EKM_0105,
    MORTALITY_SOURCE_CAVEAT,
    SUPPORTED_EK0105_TABLE_IDS,
    MortalityTable,
    load_ek0105_table,
    survival_factor,
    survival_factors,
)

__all__ = [
    "DEFAULT_EK0105_TABLE_ID",
    "EKF_0105",
    "EKM_0105",
    "MORTALITY_SOURCE_CAVEAT",
    "MortalityTable",
    "SUPPORTED_EK0105_TABLE_IDS",
    "load_ek0105_table",
    "survival_factor",
    "survival_factors",
]
