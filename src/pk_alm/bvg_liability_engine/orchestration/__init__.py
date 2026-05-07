"""BVG liability engine orchestration entrypoints.

The new generic engine (:func:`run_bvg_engine`, :class:`BVGEngineResult`) is
in :mod:`.generic_engine`. Legacy stage-specific engines remain in
:mod:`.legacy` and are still re-exported from the original module paths
(``.engine``, ``.engine_stage2``, ``.engine_stage2c``, ``.engine_stage2d``)
until the Phase 6 scenario cutover is complete.
"""

from pk_alm.bvg_liability_engine.orchestration.generic_engine import (
    BVGEngineResult,
    run_bvg_engine,
)
from pk_alm.bvg_liability_engine.orchestration.result import BVGEngineResult as _Result  # noqa: F401
from pk_alm.bvg_liability_engine.orchestration.year_step import BVGYearStep

__all__ = [
    "BVGEngineResult",
    "BVGYearStep",
    "run_bvg_engine",
]
