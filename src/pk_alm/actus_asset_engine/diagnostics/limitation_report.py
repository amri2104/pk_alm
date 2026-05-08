"""Known limitation diagnostics for AAL asset modelling."""

from __future__ import annotations

import pandas as pd

from pk_alm.actus_asset_engine.contract_config import AALContractConfig

LIMITATION_REPORT_COLUMNS = ("scope", "severity", "message")


def build_limitation_report(
    contracts: tuple[AALContractConfig, ...],
) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    if any(config.contract_type == "STK" for config in contracts):
        rows.append(
            {
                "scope": "STK",
                "severity": "warning",
                "message": (
                    "The public AAL reference server can emit STK termination "
                    "events while omitting dividend events."
                ),
            }
        )
    if any(config.contract_type == "CSH" for config in contracts):
        rows.append(
            {
                "scope": "CSH",
                "severity": "info",
                "message": (
                    "CSH contracts are included in the AAL portfolio, but the "
                    "public server emits no temporal cash events for them."
                ),
            }
        )
    return pd.DataFrame(rows, columns=list(LIMITATION_REPORT_COLUMNS))
