"""AAL Asset Engine v1 — live ACTUS asset-side cashflow engine.

This is the asset-side counterpart to the BVG liability engine. It takes a
small set of PAM, STK, and CSH contract specs, builds real AAL contracts and
a real AAL ``Portfolio``, and uses AAL's service-backed event generation API
(``PublicActusService.generateEvents``) to produce schema-valid cashflows in
the canonical CashflowRecord schema. STK dividend and CSH interest events are
synthesized as ``ACTUS_PROXY`` cashflows where the live AAL server does not
emit them.

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
from pk_alm.cashflows.schema import (
    CASHFLOW_COLUMNS,
    CashflowRecord,
    cashflow_records_to_dataframe,
    validate_cashflow_dataframe,
)

_ASSET_ENGINE_SOURCES = {"ACTUS", "ACTUS_PROXY"}
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
            raise ValueError(
                'cashflows source values must be "ACTUS" or "ACTUS_PROXY"'
            )

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


def _empty_cashflow_dataframe() -> pd.DataFrame:
    return pd.DataFrame(columns=list(CASHFLOW_COLUMNS))


def _split_specs(
    specs: tuple[AssetSpec, ...],
) -> tuple[tuple[PAMSpec, ...], tuple[STKSpec, ...], tuple[CSHSpec, ...]]:
    pam_specs = tuple(spec for spec in specs if isinstance(spec, PAMSpec))
    stk_specs = tuple(spec for spec in specs if isinstance(spec, STKSpec))
    csh_specs = tuple(spec for spec in specs if isinstance(spec, CSHSpec))
    return pam_specs, stk_specs, csh_specs


def _synthesize_stk_dividends(stk_specs: tuple[STKSpec, ...]) -> tuple[CashflowRecord, ...]:
    records: list[CashflowRecord] = []
    for spec in stk_specs:
        if spec.dividend_yield <= 0:
            continue
        for year in range(spec.start_year + 1, spec.divestment_year + 1):
            current_market_value = (
                spec.quantity
                * spec.price_at_purchase
                * ((1.0 + spec.market_value_growth) ** (year - spec.start_year))
            )
            records.append(
                CashflowRecord(
                    contractId=spec.contract_id,
                    time=f"{year}-01-01T00:00:00",
                    type="DV",
                    payoff=spec.dividend_yield * current_market_value,
                    nominalValue=current_market_value,
                    currency=spec.currency,
                    source="ACTUS_PROXY",
                )
            )
    return tuple(records)


def _synthesize_cash_interest(
    csh_specs: tuple[CSHSpec, ...],
    *,
    horizon_years: int,
) -> tuple[CashflowRecord, ...]:
    records: list[CashflowRecord] = []
    for spec in csh_specs:
        if spec.assumed_return <= 0:
            continue
        for year in range(spec.start_year + 1, spec.start_year + horizon_years + 1):
            records.append(
                CashflowRecord(
                    contractId=spec.contract_id,
                    time=f"{year}-01-01T00:00:00",
                    type="IP",
                    payoff=spec.assumed_return * spec.nominal_value,
                    nominalValue=spec.nominal_value,
                    currency=spec.currency,
                    source="ACTUS_PROXY",
                )
            )
    return tuple(records)


def _build_proxy_cashflows(
    *,
    stk_specs: tuple[STKSpec, ...],
    csh_specs: tuple[CSHSpec, ...],
    horizon_years: int,
) -> pd.DataFrame:
    records = (
        *_synthesize_stk_dividends(stk_specs),
        *_synthesize_cash_interest(csh_specs, horizon_years=horizon_years),
    )
    if not records:
        return _empty_cashflow_dataframe()
    return cashflow_records_to_dataframe(records)


def _check_no_stk_dividend_double_counting(
    *,
    server_cashflows: pd.DataFrame,
    proxy_cashflows: pd.DataFrame,
    stk_specs: tuple[STKSpec, ...],
) -> None:
    if server_cashflows.empty or proxy_cashflows.empty:
        return
    stk_ids = {spec.contract_id for spec in stk_specs}
    server_dv_ids = set(
        server_cashflows.loc[
            (server_cashflows["source"] == "ACTUS")
            & (server_cashflows["type"] == "DV")
            & (server_cashflows["contractId"].isin(stk_ids)),
            "contractId",
        ]
    )
    proxy_dv_ids = set(
        proxy_cashflows.loc[
            (proxy_cashflows["source"] == "ACTUS_PROXY")
            & (proxy_cashflows["type"] == "DV"),
            "contractId",
        ]
    )
    double_counted = sorted(server_dv_ids & proxy_dv_ids)
    if double_counted:
        raise RuntimeError(
            "STK dividend double-counting guard triggered for contract IDs: "
            f"{double_counted}. The live ACTUS server emitted DV events while "
            "the engine would also synthesize proxy DV events."
        )


def run_aal_asset_engine(
    specs: tuple[AssetSpec, ...] | list[AssetSpec] | None = None,
    *,
    horizon_years: int = 12,
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
        server_cashflows = aal_events_to_cashflow_dataframe(events_obj)
    except Exception as exc:
        raise RuntimeError(
            f"AAL event mapping to CashflowRecord schema failed: {exc}"
        ) from exc

    proxy_cashflows = _build_proxy_cashflows(
        stk_specs=stk_specs,
        csh_specs=csh_specs,
        horizon_years=horizon_years,
    )
    _check_no_stk_dividend_double_counting(
        server_cashflows=server_cashflows,
        proxy_cashflows=proxy_cashflows,
        stk_specs=stk_specs,
    )

    cashflows = pd.concat(
        [server_cashflows, proxy_cashflows],
        ignore_index=True,
    )
    if cashflows.empty:
        cashflows = _empty_cashflow_dataframe()
    else:
        cashflows = cashflows.sort_values(_SORT_COLUMNS, ignore_index=True)
    validate_cashflow_dataframe(cashflows)

    n_server = len(server_cashflows)
    n_proxy = len(proxy_cashflows)
    print(
        "[Phase2] dispatched "
        f"{len(pam_specs)} PAM + {len(stk_specs)} STK + {len(csh_specs)} CSH; "
        f"received {n_server} server events; synthesized {n_proxy} proxy events"
    )

    version = _detect_aal_version()
    version_label = version if version is not None else "unknown"
    notes = (
        f"AAL generation via PublicActusService (AAL {version_label})",
        (
            f"Processed specs: {len(pam_specs)} PAM, {len(stk_specs)} STK, "
            f"{len(csh_specs)} CSH"
        ),
        f"Server events: {n_server}; ACTUS_PROXY events: {n_proxy}",
    )
    return AALAssetEngineResult(
        cashflows=cashflows,
        contracts=resolved_specs,
        aal_version=version,
        notes=notes,
    )
