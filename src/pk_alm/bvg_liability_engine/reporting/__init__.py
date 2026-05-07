"""Reporting helpers for the BVG liability engine.

Targets four report surfaces:

- :mod:`assumption_report` — flatten :class:`BVGAssumptions` into a
  parameter / value / unit / description / source table.
- :mod:`summary_trajectory` — per-year aggregate metrics from a
  :class:`BVGEngineResult`.
- :mod:`validation_report` — pass/fail invariants on engine output.
- :mod:`thesis_tables` — pre-formatted tables for the BA write-up.

The thesis-table helpers compose these lower-level reports for the BA write-up.
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
from pk_alm.bvg_liability_engine.reporting.thesis_tables import (
    build_bvg_assumptions_table,
    build_bvg_scenario_comparison_table,
    build_bvg_summary_trajectory_table,
    build_bvg_validation_table,
    build_technical_vs_economic_liability_table,
)

__all__ = [
    "build_assumption_report",
    "build_bvg_assumptions_table",
    "build_bvg_scenario_comparison_table",
    "build_bvg_summary_trajectory_table",
    "build_bvg_validation_table",
    "build_summary_trajectory",
    "build_technical_vs_economic_liability_table",
    "build_validation_report",
]
