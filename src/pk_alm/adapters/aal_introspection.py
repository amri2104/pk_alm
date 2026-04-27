"""Optional API-surface introspection for the Awesome ACTUS Library.

This module safely inspects the optional Awesome ACTUS Library (AAL) API
surface when AAL is installed. It does not create ACTUS contracts, does not
generate AAL cashflows, and does not change the deterministic Stage-1
baseline. It is an exploratory boundary for future real AAL integration.

The project remains usable without AAL installed. This module must not import
``awesome_actus_lib`` directly at module import time.
"""

from __future__ import annotations

from dataclasses import dataclass
import inspect
import pkgutil
import types

from pk_alm.adapters.aal_probe import (
    AALAvailability,
    check_aal_availability,
    get_aal_module,
)

_SNAPSHOT_TUPLE_FIELDS = (
    "top_level_public_names",
    "public_submodules",
    "candidate_contract_symbols",
    "candidate_portfolio_symbols",
    "candidate_event_symbols",
    "candidate_analysis_symbols",
    "candidate_actus_type_symbols",
    "notes",
)

_CONTRACT_KEYWORDS = ("contract", "terms", "actus")
_PORTFOLIO_KEYWORDS = ("portfolio",)
_EVENT_KEYWORDS = ("event", "cashflow", "cash_flow", "schedule")
_ANALYSIS_KEYWORDS = ("analysis", "income", "liquidity", "value")
_ACTUS_TYPE_KEYWORDS = ("pam", "ann", "nam", "lam", "stk", "swppv", "capfl")


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


def _validate_string_tuple(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be tuple, got {type(value).__name__}")
    for i, item in enumerate(value):
        if not isinstance(item, str):
            raise TypeError(
                f"{name}[{i}] must be str, got {type(item).__name__}"
            )
    return value


@dataclass(frozen=True)
class AALAPISurfaceSnapshot:
    """Snapshot of the optional AAL module's visible API surface."""

    is_available: bool
    version: str | None
    module_name: str
    top_level_public_names: tuple[str, ...]
    public_submodules: tuple[str, ...]
    candidate_contract_symbols: tuple[str, ...]
    candidate_portfolio_symbols: tuple[str, ...]
    candidate_event_symbols: tuple[str, ...]
    candidate_analysis_symbols: tuple[str, ...]
    candidate_actus_type_symbols: tuple[str, ...]
    notes: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_bool(self.is_available, "is_available")
        _validate_optional_string(self.version, "version")
        _validate_non_empty_string(self.module_name, "module_name")
        for field_name in _SNAPSHOT_TUPLE_FIELDS:
            _validate_string_tuple(getattr(self, field_name), field_name)

    def to_dict(self) -> dict[str, object]:
        """Return snapshot fields in stable reporting order."""
        return {
            "is_available": self.is_available,
            "version": self.version,
            "module_name": self.module_name,
            "top_level_public_names": self.top_level_public_names,
            "public_submodules": self.public_submodules,
            "candidate_contract_symbols": self.candidate_contract_symbols,
            "candidate_portfolio_symbols": self.candidate_portfolio_symbols,
            "candidate_event_symbols": self.candidate_event_symbols,
            "candidate_analysis_symbols": self.candidate_analysis_symbols,
            "candidate_actus_type_symbols": self.candidate_actus_type_symbols,
            "notes": self.notes,
        }


def _public_names(obj: object) -> tuple[str, ...]:
    """Return sorted public names from ``dir(obj)`` without raising."""
    try:
        names = dir(obj)
    except Exception:
        return ()
    return tuple(sorted(name for name in names if not name.startswith("_")))


def _discover_public_submodules(module: types.ModuleType) -> tuple[str, ...]:
    """Return public direct submodule names without importing them."""
    path = getattr(module, "__path__", None)
    if path is None:
        return ()
    try:
        module_infos = pkgutil.iter_modules(path)
        return tuple(
            sorted(info.name for info in module_infos if not info.name.startswith("_"))
        )
    except Exception:
        return ()


def _filter_candidate_symbols(
    names: tuple[str, ...],
    keywords: tuple[str, ...],
) -> tuple[str, ...]:
    """Filter sorted names using case-insensitive keyword containment."""
    lowered_keywords = tuple(keyword.lower() for keyword in keywords)
    return tuple(
        name
        for name in names
        if any(keyword in name.lower() for keyword in lowered_keywords)
    )


def inspect_aal_api_surface() -> AALAPISurfaceSnapshot:
    """Inspect optional AAL API names without generating cashflows."""
    availability: AALAvailability = check_aal_availability()
    if not availability.is_available:
        return AALAPISurfaceSnapshot(
            is_available=False,
            version=None,
            module_name=availability.module_name,
            top_level_public_names=(),
            public_submodules=(),
            candidate_contract_symbols=(),
            candidate_portfolio_symbols=(),
            candidate_event_symbols=(),
            candidate_analysis_symbols=(),
            candidate_actus_type_symbols=(),
            notes=(
                "AAL is not installed; optional API surface cannot be inspected.",
                "The deterministic Stage-1 baseline remains usable without AAL.",
            ),
        )

    module = get_aal_module()
    top_level_public_names = _public_names(module)
    public_submodules = (
        _discover_public_submodules(module)
        if inspect.ismodule(module)
        else ()
    )
    candidate_pool = tuple(sorted(set(top_level_public_names + public_submodules)))

    return AALAPISurfaceSnapshot(
        is_available=True,
        version=availability.version,
        module_name=availability.module_name,
        top_level_public_names=top_level_public_names,
        public_submodules=public_submodules,
        candidate_contract_symbols=_filter_candidate_symbols(
            candidate_pool,
            _CONTRACT_KEYWORDS,
        ),
        candidate_portfolio_symbols=_filter_candidate_symbols(
            candidate_pool,
            _PORTFOLIO_KEYWORDS,
        ),
        candidate_event_symbols=_filter_candidate_symbols(
            candidate_pool,
            _EVENT_KEYWORDS,
        ),
        candidate_analysis_symbols=_filter_candidate_symbols(
            candidate_pool,
            _ANALYSIS_KEYWORDS,
        ),
        candidate_actus_type_symbols=_filter_candidate_symbols(
            candidate_pool,
            _ACTUS_TYPE_KEYWORDS,
        ),
        notes=(
            "This snapshot is introspection only.",
            "No AAL contracts are created and no AAL cashflows are generated.",
        ),
    )


def format_aal_api_surface_report(snapshot: AALAPISurfaceSnapshot) -> str:
    """Format a human-readable AAL API surface report."""
    availability_text = "available" if snapshot.is_available else "unavailable"
    lines = [
        "AAL API Surface Report",
        f"availability: {availability_text}",
        f"version: {snapshot.version if snapshot.version is not None else 'unknown'}",
        f"module_name: {snapshot.module_name}",
        f"top_level_public_names_count: {len(snapshot.top_level_public_names)}",
        f"public_submodules_count: {len(snapshot.public_submodules)}",
        "candidate_contract_symbols: "
        + ", ".join(snapshot.candidate_contract_symbols),
        "candidate_portfolio_symbols: "
        + ", ".join(snapshot.candidate_portfolio_symbols),
        "candidate_event_symbols: " + ", ".join(snapshot.candidate_event_symbols),
        "candidate_analysis_symbols: "
        + ", ".join(snapshot.candidate_analysis_symbols),
        "candidate_actus_type_symbols: "
        + ", ".join(snapshot.candidate_actus_type_symbols),
        "notes:",
    ]
    lines.extend(f"- {note}" for note in snapshot.notes)
    if not snapshot.is_available:
        lines.append("AAL is optional; install it only for future real integration.")
    return "\n".join(lines)
