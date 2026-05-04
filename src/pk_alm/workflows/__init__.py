"""User-facing workflow helpers for pk_alm.

Attributes are loaded lazily so Streamlit/import smoke tests do not require
optional ACTUS dependencies unless the Full ALM workflow is actually used.
"""

from __future__ import annotations

from typing import Any

_FULL_ALM_EXPORTS = {
    "FullALMWorkflowResult",
    "run_full_alm_reporting_workflow",
    "summarize_generated_outputs",
}

_STAGE_APP_EXPORTS = {
    "MODE_METADATA",
    "STREAMLIT_OUTPUT_DIRS",
    "StageAppRunResult",
    "run_stage",
    "summarize_available_outputs",
}

__all__ = sorted(_FULL_ALM_EXPORTS | _STAGE_APP_EXPORTS)


def __getattr__(name: str) -> Any:
    if name in _FULL_ALM_EXPORTS:
        from pk_alm.workflows import full_alm_workflow

        return getattr(full_alm_workflow, name)
    if name in _STAGE_APP_EXPORTS:
        from pk_alm.workflows import stage_app_workflow

        return getattr(stage_app_workflow, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
