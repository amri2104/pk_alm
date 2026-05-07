"""Compatibility shim: re-exports the legacy stage-2D stochastic engine."""

from pk_alm.bvg_liability_engine.orchestration.legacy.engine_stage2d import *  # noqa: F401,F403
from pk_alm.bvg_liability_engine.orchestration.legacy.engine_stage2d import (  # noqa: F401
    Stage2DEngineResult,
    run_bvg_engine_stage2d,
)
