"""Compatibility shim: re-exports the legacy stage-2C engine."""

from pk_alm.bvg_liability_engine.orchestration.legacy.engine_stage2c import *  # noqa: F401,F403
from pk_alm.bvg_liability_engine.orchestration.legacy.engine_stage2c import (  # noqa: F401
    Stage2CEngineResult,
    run_bvg_engine_stage2c,
)
