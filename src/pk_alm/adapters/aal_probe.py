"""Optional availability probe for the Awesome ACTUS Library.

This module probes whether the Awesome ACTUS Library (AAL) is available in
the current Python environment. It does not generate real AAL cashflows yet,
does not change the deterministic Stage-1 baseline, and exists only as a
feasibility boundary for a later AAL integration sprint.

The project must remain usable without AAL installed. For that reason this
module must not import ``awesome_actus_lib`` at module import time; all real
AAL imports go through :func:`get_aal_module`.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import importlib.metadata
from types import ModuleType
from typing import Any

AAL_MODULE_NAME = "awesome_actus_lib"
AAL_DISTRIBUTION_NAMES = ("awesome_actus_lib", "awesome-actus-lib")


def _validate_bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be bool, got {type(value).__name__}")
    return value


def _validate_non_empty_string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str, got {type(value).__name__}")
    if not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _validate_optional_string(value: object, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str or None, got {type(value).__name__}")
    return value


def _validate_distribution_names(value: object) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(
            f"distribution_names must be tuple, got {type(value).__name__}"
        )
    if not value:
        raise ValueError("distribution_names must be non-empty")
    for i, item in enumerate(value):
        _validate_non_empty_string(item, f"distribution_names[{i}]")
    return value


@dataclass(frozen=True)
class AALAvailability:
    """Optional AAL availability status."""

    is_available: bool
    module_name: str
    distribution_names: tuple[str, ...]
    version: str | None
    import_error: str | None

    def __post_init__(self) -> None:
        _validate_bool(self.is_available, "is_available")
        _validate_non_empty_string(self.module_name, "module_name")
        _validate_distribution_names(self.distribution_names)
        _validate_optional_string(self.version, "version")
        _validate_optional_string(self.import_error, "import_error")

        if self.is_available and self.import_error is not None:
            raise ValueError("import_error must be None when is_available is True")

    def to_dict(self) -> dict[str, object]:
        """Return status fields in stable reporting order."""
        return {
            "is_available": self.is_available,
            "module_name": self.module_name,
            "distribution_names": self.distribution_names,
            "version": self.version,
            "import_error": self.import_error,
        }


def _detect_aal_version() -> str | None:
    """Return the installed AAL distribution version if metadata is available."""
    for name in AAL_DISTRIBUTION_NAMES:
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return None


def check_aal_availability() -> AALAvailability:
    """Check optional AAL availability without requiring it to be installed."""
    try:
        importlib.import_module(AAL_MODULE_NAME)
    except ImportError as error:
        return AALAvailability(
            is_available=False,
            module_name=AAL_MODULE_NAME,
            distribution_names=AAL_DISTRIBUTION_NAMES,
            version=None,
            import_error=str(error),
        )

    return AALAvailability(
        is_available=True,
        module_name=AAL_MODULE_NAME,
        distribution_names=AAL_DISTRIBUTION_NAMES,
        version=_detect_aal_version(),
        import_error=None,
    )


def require_aal_available() -> AALAvailability:
    """Return AAL availability or raise a clear optional-dependency error."""
    availability = check_aal_availability()
    if availability.is_available:
        return availability

    raise ImportError(
        "The Awesome ACTUS Library (AAL) is optional. Install it with "
        "`pip install awesome-actus-lib` only when real AAL integration is "
        "needed. The Stage-1 baseline, ACTUS-style fixtures, and asset "
        "overlay scenario do not require AAL."
    )


def get_aal_module() -> ModuleType | Any:
    """Import and return the optional AAL module through the approved gateway."""
    require_aal_available()
    return importlib.import_module(AAL_MODULE_NAME)
