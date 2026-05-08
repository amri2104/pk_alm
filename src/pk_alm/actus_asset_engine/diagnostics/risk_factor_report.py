"""Risk-factor diagnostics for AAL runs."""

from __future__ import annotations

import pandas as pd

from pk_alm.actus_asset_engine.risk_factors import AALRiskFactorSet

RISK_FACTOR_REPORT_COLUMNS = (
    "marketObjectCode",
    "className",
    "row_count",
    "has_to_json",
)


def _row_count(risk_factor: object) -> int | None:
    data = getattr(risk_factor, "_data", None)
    if data is not None and hasattr(data, "__len__"):
        return int(len(data))
    to_json = getattr(risk_factor, "to_json", None)
    if callable(to_json):
        try:
            payload = to_json()
        except Exception:
            return None
        json_data = payload.get("data") if isinstance(payload, dict) else None
        if hasattr(json_data, "__len__"):
            return int(len(json_data))
    source = getattr(risk_factor, "source", None)
    if source is not None and hasattr(source, "__len__"):
        return int(len(source))
    return None


def build_risk_factor_report(risk_factors: AALRiskFactorSet) -> pd.DataFrame:
    rows = []
    for risk_factor in risk_factors.risk_factors:
        rows.append(
            {
                "marketObjectCode": getattr(risk_factor, "marketObjectCode", ""),
                "className": type(risk_factor).__name__,
                "row_count": _row_count(risk_factor),
                "has_to_json": callable(getattr(risk_factor, "to_json", None)),
            }
        )
    return pd.DataFrame(rows, columns=list(RISK_FACTOR_REPORT_COLUMNS))
