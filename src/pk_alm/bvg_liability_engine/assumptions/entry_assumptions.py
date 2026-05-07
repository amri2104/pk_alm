"""Re-export the existing :class:`EntryAssumptions` from population_dynamics.

Kept as a thin shim so ``BVGAssumptions`` can compose the canonical entry
assumption type without duplicating its definition.
"""

from pk_alm.bvg_liability_engine.population_dynamics.entry_dynamics import (
    DEFAULT_ENTRY_AGE,
    DEFAULT_ENTRY_CAPITAL_PER_PERSON,
    DEFAULT_ENTRY_COHORT_ID_PREFIX,
    DEFAULT_ENTRY_COUNT_PER_YEAR,
    DEFAULT_ENTRY_GROSS_SALARY,
    EntryAssumptions,
    get_default_entry_assumptions,
)

__all__ = [
    "DEFAULT_ENTRY_AGE",
    "DEFAULT_ENTRY_CAPITAL_PER_PERSON",
    "DEFAULT_ENTRY_COHORT_ID_PREFIX",
    "DEFAULT_ENTRY_COUNT_PER_YEAR",
    "DEFAULT_ENTRY_GROSS_SALARY",
    "EntryAssumptions",
    "get_default_entry_assumptions",
]
