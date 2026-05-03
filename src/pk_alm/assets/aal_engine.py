"""AAL Asset Engine v1 — live ACTUS asset-side cashflow engine.

This is the asset-side counterpart to the BVG liability engine. It takes a
small set of PAM, STK, and CSH contract specs, builds real AAL contracts and
a real AAL ``Portfolio``, and uses AAL's service-backed event generation API
(``PublicActusService.generateEvents``) to produce schema-valid cashflows in
the canonical CashflowRecord schema. The engine records only real AAL server
responses: PAM contracts emit IP/MD, STK contracts emit TD but no DV on the
tested public reference server, and CSH contracts emit no temporal events.

``awesome_actus_lib`` is a required project dependency. There is no fixture
cashflow path and no generation-mode switch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import importlib.metadata

import pandas as pd

from pk_alm.adapters.aal_asset_portfolio import (
    AALAssetContractSpec,
    AssetSpec,
    CSHSpec,
    PAMSpec,
    STKSpec,
    build_aal_portfolio_from_specs,
    get_default_aal_asset_contract_specs,
    validate_aal_asset_contract_specs,
)
from pk_alm.adapters.aal_probe import get_aal_module
from pk_alm.adapters.actus_adapter import aal_events_to_cashflow_dataframe
from pk_alm.cashflows.schema import validate_cashflow_dataframe

_ASSET_ENGINE_SOURCES = {"ACTUS"}
_SORT_COLUMNS = ["time", "contractId", "type", "source"]


def _detect_aal_version() -> str | None:
    for distribution_name in ("awesome_actus_lib", "awesome-actus-lib"):
        try:
            return importlib.metadata.version(distribution_name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return None


@dataclass(frozen=True)
class AALAssetEngineResult:
    """Result of one live AAL Asset Engine run."""

    cashflows: pd.DataFrame
    contracts: tuple[AALAssetContractSpec, ...]
    aal_version: str | None
    notes: tuple[str, ...]
    generation_mode: str = field(default="aal")
    aal_available: bool = field(default=True)

    def __post_init__(self) -> None:
        if not isinstance(self.cashflows, pd.DataFrame):
            raise TypeError(
                f"cashflows must be a pandas DataFrame, "
                f"got {type(self.cashflows).__name__}"
            )
        validate_cashflow_dataframe(self.cashflows)
        if not self.cashflows.empty and not set(self.cashflows["source"]).issubset(
            _ASSET_ENGINE_SOURCES
        ):
            raise ValueError('cashflows source values must be "ACTUS"')

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

        if self.generation_mode != "aal":
            raise ValueError('generation_mode is fixed to "aal"')
        if self.aal_available is not True:
            raise ValueError("aal_available is fixed to True")


def _resolve_specs(
    specs: tuple[AssetSpec, ...] | list[AssetSpec] | None,
) -> tuple[AssetSpec, ...]:
    if specs is None:
        return validate_aal_asset_contract_specs(
            get_default_aal_asset_contract_specs()
        )
    return validate_aal_asset_contract_specs(specs)


def _split_specs(
    specs: tuple[AssetSpec, ...],
) -> tuple[tuple[PAMSpec, ...], tuple[STKSpec, ...], tuple[CSHSpec, ...]]:
    pam_specs = tuple(spec for spec in specs if isinstance(spec, PAMSpec))
    stk_specs = tuple(spec for spec in specs if isinstance(spec, STKSpec))
    csh_specs = tuple(spec for spec in specs if isinstance(spec, CSHSpec))
    return pam_specs, stk_specs, csh_specs


def run_aal_asset_engine(
    specs: tuple[AssetSpec, ...] | list[AssetSpec] | None = None,
) -> AALAssetEngineResult:
    """Run the required live AAL Asset Engine.

    Raises:
        ValueError: if the specs are invalid.
        RuntimeError: if AAL contract construction, portfolio construction,
            service-backed event generation, or schema mapping fails.
    """
    resolved_specs = _resolve_specs(specs)
    pam_specs, stk_specs, csh_specs = _split_specs(resolved_specs)
    module = get_aal_module()

    try:
        portfolio = build_aal_portfolio_from_specs(module, resolved_specs)
    except Exception as exc:
        raise RuntimeError(
            f"AAL contract or Portfolio construction failed: {exc}"
        ) from exc

    try:
        service = module.PublicActusService()
        events_obj = service.generateEvents(portfolio=portfolio)
    except Exception as exc:
        raise RuntimeError(
            f"AAL event generation via PublicActusService failed: {exc}. "
            f"The live ACTUS service endpoint must be reachable for "
            f"asset-side ACTUS cashflow generation."
        ) from exc

    try:
        cashflows = aal_events_to_cashflow_dataframe(events_obj)
    except Exception as exc:
        raise RuntimeError(
            f"AAL event mapping to CashflowRecord schema failed: {exc}"
        ) from exc

    if not cashflows.empty:
        cashflows = cashflows.sort_values(_SORT_COLUMNS, ignore_index=True)
    validate_cashflow_dataframe(cashflows)

    n_server = len(cashflows)
    print(
        "[Phase2] dispatched "
        f"{len(pam_specs)} PAM + {len(stk_specs)} STK + {len(csh_specs)} CSH; "
        f"received {n_server} server events"
    )

    version = _detect_aal_version()
    version_label = version if version is not None else "unknown"
    notes = (
        f"AAL generation via PublicActusService (AAL {version_label})",
        (
            f"Processed specs: {len(pam_specs)} PAM, {len(stk_specs)} STK, "
            f"{len(csh_specs)} CSH"
        ),
        "Asset-side events come from the live AAL server only. STK contracts "
        "return TD events but no DV events on the public AAL reference server; "
        "CSH contracts return no temporal events. These are documented "
        "AAL/server limitations and are not compensated by synthetic cashflows.",
        f"Server events: {n_server}",
    )
    return AALAssetEngineResult(
        cashflows=cashflows,
        contracts=resolved_specs,
        aal_version=version,
        notes=notes,
    )
