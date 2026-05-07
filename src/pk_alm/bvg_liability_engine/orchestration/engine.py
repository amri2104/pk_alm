"""Compatibility shim: re-exports the legacy stage-1 engine.

The new generic engine lives in
:mod:`pk_alm.bvg_liability_engine.orchestration.generic_engine` and is the
target of the Phase 6 scenario cutover. Until then, all existing imports of
``orchestration.engine`` resolve to the legacy stage-1 implementation.
"""

from pk_alm.bvg_liability_engine.orchestration.legacy.engine import *  # noqa: F401,F403
from pk_alm.bvg_liability_engine.orchestration.legacy.engine import (  # noqa: F401
    BVGEngineResult,
    run_bvg_engine,
)
