"""ACTUS/AAL asset-side cashflow engine.

The engine separates ACTUS contract terms, risk factors, and simulation
cut-off settings. Contract configs are passed to real AAL contract classes,
risk factors are forwarded through ``PublicActusService.generateEvents`` as
``riskFactors=``, and output cashflows are filtered to the forward-looking
ALM horizon by default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import importlib.metadata

import pandas as pd

from pk_alm.actus_asset_engine.aal_asset_portfolio import (
    get_default_aal_asset_contract_configs,
)
from pk_alm.actus_asset_engine.aal_probe import get_aal_module
from pk_alm.actus_asset_engine.actus_adapter import aal_events_to_cashflow_dataframe
from pk_alm.actus_asset_engine.contract_config import (
    AALContractConfig,
    build_aal_portfolio_from_configs,
    validate_aal_contract_configs,
)
from pk_alm.actus_asset_engine.diagnostics import (
    build_event_coverage_report,
    build_event_summary,
    build_limitation_report,
    build_risk_factor_report,
)
from pk_alm.actus_asset_engine.filters import (
    filter_cashflows_for_settings,
    validate_historical_initial_exchange_cutoff,
)
from pk_alm.actus_asset_engine.risk_factors import (
    AALRiskFactorSet,
    coerce_aal_risk_factor_set,
)
from pk_alm.actus_asset_engine.simulation_settings import (
    AALSimulationSettings,
    default_aal_simulation_settings,
)
from pk_alm.cashflows.schema import validate_cashflow_dataframe

_ASSET_ENGINE_SOURCES = {"ACTUS"}


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
    contracts: tuple[AALContractConfig, ...]
    risk_factors: AALRiskFactorSet
    settings: AALSimulationSettings
    event_summary: pd.DataFrame
    event_coverage_report: pd.DataFrame
    risk_factor_report: pd.DataFrame
    limitation_report: pd.DataFrame
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

        validate_aal_contract_configs(self.contracts)
        if not isinstance(self.risk_factors, AALRiskFactorSet):
            raise TypeError(
                "risk_factors must be AALRiskFactorSet, "
                f"got {type(self.risk_factors).__name__}"
            )
        if not isinstance(self.settings, AALSimulationSettings):
            raise TypeError(
                f"settings must be AALSimulationSettings, "
                f"got {type(self.settings).__name__}"
            )
        for name in (
            "event_summary",
            "event_coverage_report",
            "risk_factor_report",
            "limitation_report",
        ):
            if not isinstance(getattr(self, name), pd.DataFrame):
                raise TypeError(f"{name} must be a pandas DataFrame")

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


def _resolve_contracts(
    contracts: tuple[AALContractConfig, ...] | list[AALContractConfig] | None,
) -> tuple[AALContractConfig, ...]:
    if contracts is None:
        return validate_aal_contract_configs(
            get_default_aal_asset_contract_configs()
        )
    return validate_aal_contract_configs(contracts)


def _resolve_settings(
    settings: AALSimulationSettings | None,
) -> AALSimulationSettings:
    if settings is None:
        return default_aal_simulation_settings()
    if not isinstance(settings, AALSimulationSettings):
        raise TypeError(
            f"settings must be AALSimulationSettings, got {type(settings).__name__}"
        )
    return settings


def _contract_type_counts(contracts: tuple[AALContractConfig, ...]) -> str:
    counts = {
        contract_type: sum(
            config.contract_type == contract_type for config in contracts
        )
        for contract_type in sorted({config.contract_type for config in contracts})
    }
    return ", ".join(f"{count} {contract_type}" for contract_type, count in counts.items())


def run_aal_asset_engine(
    contracts: tuple[AALContractConfig, ...] | list[AALContractConfig] | None = None,
    risk_factors: AALRiskFactorSet | tuple[object, ...] | list[object] | None = None,
    settings: AALSimulationSettings | None = None,
) -> AALAssetEngineResult:
    """Run the live AAL Asset Engine with ACTUS-native inputs.

    Args:
        contracts: ACTUS-native contract configs. Defaults to the thesis
            pension-fund asset portfolio.
        risk_factors: AAL risk factors, forwarded as ``riskFactors=``. ``None``
            means no risk factors are supplied.
        settings: simulation date window and cut-off behavior.

    Raises:
        ValueError: if inputs are invalid.
        RuntimeError: if AAL construction, event generation, mapping, or
            filtering fails.
    """
    resolved_contracts = _resolve_contracts(contracts)
    resolved_risk_factors = coerce_aal_risk_factor_set(risk_factors)
    resolved_settings = _resolve_settings(settings)
    module = get_aal_module()

    try:
        portfolio = build_aal_portfolio_from_configs(module, resolved_contracts)
    except Exception as exc:
        raise RuntimeError(
            f"AAL contract or Portfolio construction failed: {exc}"
        ) from exc

    try:
        service = module.PublicActusService()
        events_obj = service.generateEvents(
            portfolio=portfolio,
            riskFactors=resolved_risk_factors.to_aal_argument(),
        )
    except Exception as exc:
        raise RuntimeError(
            f"AAL event generation via PublicActusService failed: {exc}. "
            f"The live ACTUS service endpoint must be reachable for "
            f"asset-side ACTUS cashflow generation."
        ) from exc

    try:
        cashflows = aal_events_to_cashflow_dataframe(events_obj)
        cashflows = filter_cashflows_for_settings(cashflows, resolved_settings)
        validate_historical_initial_exchange_cutoff(
            resolved_contracts,
            cashflows,
            resolved_settings,
        )
    except Exception as exc:
        raise RuntimeError(
            f"AAL event mapping/filtering to CashflowRecord schema failed: {exc}"
        ) from exc

    validate_cashflow_dataframe(cashflows)
    event_summary = build_event_summary(cashflows)
    coverage = build_event_coverage_report(
        resolved_contracts,
        cashflows,
        resolved_settings,
    )
    risk_report = build_risk_factor_report(resolved_risk_factors)
    limitations = build_limitation_report(resolved_contracts)

    version = _detect_aal_version()
    version_label = version if version is not None else "unknown"
    n_server = len(cashflows)
    notes = (
        f"AAL generation via PublicActusService (AAL {version_label})",
        f"Processed contract configs: {_contract_type_counts(resolved_contracts)}",
        (
            "Cashflow cut-off: "
            f"{resolved_settings.cashflow_cutoff_mode} "
            f"[{resolved_settings.event_start_date.date()} .. "
            f"{resolved_settings.event_end_date.date()}]"
        ),
        f"Risk factors supplied: {len(resolved_risk_factors.risk_factors)}",
        f"Output events after cut-off: {n_server}",
    )
    return AALAssetEngineResult(
        cashflows=cashflows,
        contracts=resolved_contracts,
        risk_factors=resolved_risk_factors,
        settings=resolved_settings,
        event_summary=event_summary,
        event_coverage_report=coverage,
        risk_factor_report=risk_report,
        limitation_report=limitations,
        aal_version=version,
        notes=notes,
    )
