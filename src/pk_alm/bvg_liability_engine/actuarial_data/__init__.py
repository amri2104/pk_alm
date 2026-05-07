"""Raw actuarial data (mortality tables, etc.) for the BVG engine.

This subpackage is the long-term home for actuarial data and its loaders.
For backwards-compatibility during the refactor it currently re-exports the
EK 0105 loader from :mod:`pk_alm.bvg_liability_engine.actuarial_assumptions.mortality`.
The CSV files will be physically relocated in Phase 7.
"""

from pk_alm.bvg_liability_engine.actuarial_data.mortality_tables import (
    EKF_0105,
    EKM_0105,
    SUPPORTED_EK0105_TABLE_IDS,
    MortalityTable,
    load_ek0105_table,
)

__all__ = [
    "EKF_0105",
    "EKM_0105",
    "MortalityTable",
    "SUPPORTED_EK0105_TABLE_IDS",
    "load_ek0105_table",
]
