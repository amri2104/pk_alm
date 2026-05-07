"""Reporting helpers for the BVG liability engine.

Targets four report surfaces:

- :mod:`assumption_report` — flatten :class:`BVGAssumptions` into a
  parameter / value / unit / description / source table.
- :mod:`summary_trajectory` — per-year aggregate metrics from a
  :class:`BVGEngineResult`.
- :mod:`validation_report` — pass/fail invariants on engine output.
- :mod:`thesis_tables` — pre-formatted tables for the BA write-up.

Currently only the trajectory and assumption reports are implemented;
validation and thesis tables are placeholders pending the next session.
"""

from pk_alm.bvg_liability_engine.reporting.assumption_report import (
    build_assumption_report,
)
from pk_alm.bvg_liability_engine.reporting.summary_trajectory import (
    build_summary_trajectory,
)
from pk_alm.bvg_liability_engine.reporting.validation_report import (
    build_validation_report,
)

__all__ = [
    "build_assumption_report",
    "build_summary_trajectory",
    "build_validation_report",
]
