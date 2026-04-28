"""AAL Asset Engine v1 — strategic asset-side cashflow engine.

This is the asset-side counterpart to the BVG liability engine. It takes a
small set of PAM-like contract specs, builds real AAL contracts and a real
AAL ``Portfolio`` when AAL is installed, and uses AAL's normal event
generation API (``PublicActusService.generateEvents``) to produce
schema-valid cashflows in the canonical CashflowRecord schema.

Generation modes are explicit:

- ``generation_mode="aal"`` is the conceptual main path. It requires AAL.
  AAL absence raises ``ImportError``; any failure inside the AAL path
  (PAM construction, Portfolio build, service call, event mapping) raises
  ``RuntimeError``. There is no silent fallback.
- ``generation_mode="fallback"`` is an explicit non-AAL path that uses the
  existing offline ACTUS-fixture cashflows. It is intended for tests,
  comparison, and development environments without AAL.

The engine never modifies ``run_stage1_baseline(...)``, the BVG modules,
or the seven default Stage-1 CSV outputs.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from pk_alm.adapters.aal_asset_boundary import build_aal_portfolio
from pk_alm.adapters.aal_asset_portfolio import (
    AALAssetContractSpec,
    build_aal_asset_portfolio_fallback_cashflows,
    build_aal_pam_contracts_from_specs,
    get_default_aal_asset_contract_specs,
    validate_aal_asset_contract_specs,
)
from pk_alm.adapters.aal_probe import check_aal_availability, get_aal_module
from pk_alm.adapters.actus_adapter import aal_events_to_cashflow_dataframe
from pk_alm.cashflows.schema import validate_cashflow_dataframe

VALID_GENERATION_MODES: tuple[str, ...] = ("aal", "fallback")


@dataclass(frozen=True)
class AALAssetEngineResult:
    """Result of one AAL Asset Engine run."""

    cashflows: pd.DataFrame
    contracts: tuple[AALAssetContractSpec, ...]
    generation_mode: str
    aal_available: bool
    aal_version: str | None
    notes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.cashflows, pd.DataFrame):
            raise TypeError(
                f"cashflows must be a pandas DataFrame, "
                f"got {type(self.cashflows).__name__}"
            )
        validate_cashflow_dataframe(self.cashflows)
        if not self.cashflows.empty and not (
            self.cashflows["source"] == "ACTUS"
        ).all():
            raise ValueError('cashflows source values must all be "ACTUS"')

        if not isinstance(self.contracts, tuple):
            raise TypeError(
                f"contracts must be a tuple, got {type(self.contracts).__name__}"
            )
        for i, contract in enumerate(self.contracts):
            if not isinstance(contract, AALAssetContractSpec):
                raise TypeError(
                    f"contracts[{i}] must be AALAssetContractSpec, "
                    f"got {type(contract).__name__}"
                )

        if self.generation_mode not in VALID_GENERATION_MODES:
            raise ValueError(
                f"generation_mode must be one of {VALID_GENERATION_MODES}, "
                f"got {self.generation_mode!r}"
            )

        if not isinstance(self.aal_available, bool):
            raise TypeError(
                f"aal_available must be bool, "
                f"got {type(self.aal_available).__name__}"
            )

        if self.aal_version is not None and not isinstance(self.aal_version, str):
            raise TypeError(
                f"aal_version must be str or None, "
                f"got {type(self.aal_version).__name__}"
            )

        if not isinstance(self.notes, tuple):
            raise TypeError(
                f"notes must be a tuple, got {type(self.notes).__name__}"
            )
        for i, note in enumerate(self.notes):
            if not isinstance(note, str):
                raise TypeError(
                    f"notes[{i}] must be str, got {type(note).__name__}"
                )


def _resolve_specs(
    specs: tuple[AALAssetContractSpec, ...]
    | list[AALAssetContractSpec]
    | None,
) -> tuple[AALAssetContractSpec, ...]:
    if specs is None:
        return validate_aal_asset_contract_specs(
            get_default_aal_asset_contract_specs()
        )
    return validate_aal_asset_contract_specs(specs)


def _run_fallback(
    specs: tuple[AALAssetContractSpec, ...],
    aal_available: bool,
    aal_version: str | None,
) -> AALAssetEngineResult:
    cashflows = build_aal_asset_portfolio_fallback_cashflows(specs)
    notes = (
        "explicit fallback mode: cashflows generated from ACTUS-style "
        "fixed-rate bond fixtures via the offline adapter; AAL was not used "
        "for event generation",
    )
    return AALAssetEngineResult(
        cashflows=cashflows,
        contracts=specs,
        generation_mode="fallback",
        aal_available=aal_available,
        aal_version=aal_version,
        notes=notes,
    )


def _run_aal(
    specs: tuple[AALAssetContractSpec, ...],
    aal_version: str | None,
) -> AALAssetEngineResult:
    module = get_aal_module()

    try:
        pam_contracts = build_aal_pam_contracts_from_specs(module, specs)
    except Exception as exc:
        raise RuntimeError(
            f"AAL PAM contract construction failed: {exc}"
        ) from exc

    try:
        portfolio = build_aal_portfolio(module, list(pam_contracts))
    except Exception as exc:
        raise RuntimeError(
            f"AAL Portfolio construction failed: {exc}"
        ) from exc

    try:
        service = module.PublicActusService()
        events_obj = service.generateEvents(portfolio=portfolio)
    except Exception as exc:
        raise RuntimeError(
            f"AAL event generation via PublicActusService failed: {exc}. "
            f"This typically means the configured ACTUS service endpoint is "
            f"unreachable. To run offline, call the engine with "
            f"generation_mode='fallback' explicitly."
        ) from exc

    try:
        cashflows = aal_events_to_cashflow_dataframe(events_obj)
    except Exception as exc:
        raise RuntimeError(
            f"AAL event mapping to CashflowRecord schema failed: {exc}"
        ) from exc

    version_label = aal_version if aal_version is not None else "unknown"
    notes = (
        f"AAL generation via PublicActusService (AAL {version_label})",
    )
    return AALAssetEngineResult(
        cashflows=cashflows,
        contracts=specs,
        generation_mode="aal",
        aal_available=True,
        aal_version=aal_version,
        notes=notes,
    )


def run_aal_asset_engine(
    specs: tuple[AALAssetContractSpec, ...]
    | list[AALAssetContractSpec]
    | None = None,
    *,
    generation_mode: str = "aal",
) -> AALAssetEngineResult:
    """Run the AAL Asset Engine in the requested mode.

    The default mode is ``"aal"``: this requires the ``awesome-actus-lib``
    package to be installed and uses AAL's normal service-backed event
    generation API. ``"fallback"`` is an explicit non-AAL mode for tests
    and offline environments.

    Raises:
        ValueError: if ``generation_mode`` is not in
            ``VALID_GENERATION_MODES`` or if the specs are invalid.
        ImportError: if ``generation_mode="aal"`` is requested and AAL is
            not installed.
        RuntimeError: if any step inside the AAL path fails.
    """
    if generation_mode not in VALID_GENERATION_MODES:
        raise ValueError(
            f"generation_mode must be one of {VALID_GENERATION_MODES}, "
            f"got {generation_mode!r}"
        )

    resolved_specs = _resolve_specs(specs)
    availability = check_aal_availability()

    if generation_mode == "fallback":
        return _run_fallback(
            resolved_specs,
            aal_available=availability.is_available,
            aal_version=availability.version,
        )

    if not availability.is_available:
        raise ImportError(
            "run_aal_asset_engine(generation_mode='aal') requires the "
            "awesome-actus-lib package to be installed. Install it with "
            "`pip install awesome-actus-lib` or `pip install pk-alm[aal]`. "
            "If you intentionally want offline cashflows, call the engine "
            "with generation_mode='fallback' instead. "
            f"Original import error: {availability.import_error}"
        )

    return _run_aal(resolved_specs, aal_version=availability.version)
