"""One-shot live AAL/ACTUS probe for PAM, STK, and CSH contracts.

This script is intentionally diagnostic only. It requires the optional
``awesome_actus_lib`` package and calls the live AAL/ACTUS service through
``PublicActusService.generateEvents``. There is no fallback path.
"""

from __future__ import annotations

from pathlib import Path
from pprint import pformat
import sys
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pk_alm.adapters.aal_probe import get_aal_module
from pk_alm.adapters.actus_adapter import aal_events_to_cashflow_dataframe


def _format_error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def _status(ok: bool, reason: str | None = None) -> str:
    if ok:
        return "OK"
    if reason is None:
        return "FAILED"
    return f"FAILED ({reason})"


def _pam_terms() -> dict[str, object]:
    return {
        "contractDealDate": "2026-01-01T00:00:00",
        "contractID": "PROBE_PAM",
        "contractRole": "RPA",
        "counterpartyID": "COUNTERPARTY_PROBE",
        "creatorID": "PK_ALM_PROBE",
        "currency": "CHF",
        "dayCountConvention": "30E360",
        "initialExchangeDate": "2026-01-01T00:00:00",
        "maturityDate": "2028-12-31T00:00:00",
        "nominalInterestRate": 0.02,
        "notionalPrincipal": 100000.0,
        "statusDate": "2026-01-01T00:00:00",
    }


def _pam_with_cycle_terms() -> dict[str, object]:
    terms = _pam_terms()
    terms.update(
        {
            "contractID": "PROBE_PAM_WITH_CYCLE",
            "cycleAnchorDateOfInterestPayment": "2027-01-01T00:00:00",
            "cycleOfInterestPayment": "P1YL1",
        }
    )
    return terms


def _stk_terms() -> dict[str, object]:
    return {
        "contractDealDate": "2026-01-01T00:00:00",
        "contractID": "PROBE_STK",
        "contractRole": "RPA",
        "counterpartyID": "COUNTERPARTY_PROBE",
        "creatorID": "PK_ALM_PROBE",
        "currency": "CHF",
        "cycleAnchorDateOfDividend": "2026-12-31T00:00:00",
        "cycleOfDividend": "P1YL1",
        "initialExchangeDate": "2026-01-01T00:00:00",
        "nextDividendPaymentAmount": 2000.0,
        "notionalPrincipal": 100000.0,
        "priceAtPurchaseDate": 100000.0,
        "priceAtTerminationDate": 100000.0,
        "purchaseDate": "2026-01-01T00:00:00",
        "quantity": 1000.0,
        "statusDate": "2026-01-01T00:00:00",
        "terminationDate": "2028-12-31T00:00:00",
    }


def _csh_terms() -> dict[str, object]:
    return {
        "contractDealDate": "2026-01-01T00:00:00",
        "contractID": "PROBE_CSH",
        "contractRole": "RPA",
        "counterpartyID": "COUNTERPARTY_PROBE",
        "creatorID": "PK_ALM_PROBE",
        "currency": "CHF",
        "initialExchangeDate": "2026-01-01T00:00:00",
        "notionalPrincipal": 50000.0,
        "statusDate": "2026-01-01T00:00:00",
    }


def _csh_with_interest_terms() -> dict[str, object]:
    terms = _csh_terms()
    terms.update(
        {
            "contractID": "PROBE_CSH_WITH_INTEREST",
            "contractDealDate": "2026-01-01T00:00:00",
            "cycleAnchorDateOfInterestPayment": "2027-01-01T00:00:00",
            "cycleOfInterestPayment": "P1YL1",
            "dayCountConvention": "30E360",
            "maturityDate": "2028-12-31T00:00:00",
            "nominalInterestRate": 0.0025,
        }
    )
    return terms


def _to_records(events: object) -> list[dict[str, object]]:
    extracted = events
    if (
        not isinstance(extracted, (dict, list, tuple, pd.DataFrame))
        and hasattr(extracted, "events_df")
    ):
        extracted = extracted.events_df

    if isinstance(extracted, pd.DataFrame):
        return extracted.to_dict(orient="records")

    if isinstance(extracted, dict):
        for key in ("events", "eventList", "results", "data"):
            value = extracted.get(key)
            if isinstance(value, (list, tuple)):
                return [item for item in value if isinstance(item, dict)]
        return [extracted]

    if isinstance(extracted, (list, tuple)):
        return [item for item in extracted if isinstance(item, dict)]

    if hasattr(extracted, "to_dict"):
        converted = extracted.to_dict()
        if isinstance(converted, pd.DataFrame):
            return converted.to_dict(orient="records")
        if isinstance(converted, dict):
            return [converted]
        if isinstance(converted, (list, tuple)):
            return [item for item in converted if isinstance(item, dict)]

    return []


def _first_present(record: dict[str, object], keys: tuple[str, ...]) -> object | None:
    for key in keys:
        if key in record:
            return record[key]
    return None


def _event_types(records: list[dict[str, object]]) -> list[str]:
    values = {
        str(value)
        for record in records
        if (value := _first_present(record, ("eventType", "event_type", "type"))) is not None
    }
    return sorted(values)


def _event_timestamps(records: list[dict[str, object]]) -> list[str]:
    values = [
        str(value)
        for record in records
        if (value := _first_present(record, ("eventDate", "event_date", "time"))) is not None
    ]
    return values


def _print_sample_events(records: list[dict[str, object]]) -> None:
    sample = records[:3]
    if not sample:
        print("Sample events: []")
        return
    print("Sample events:")
    print(pformat(sample, width=100, sort_dicts=True))


def _construct_contract(module: Any, contract_type: str) -> object:
    if contract_type == "PAM":
        return module.PAM(**_pam_terms())
    if contract_type == "PAM-WITH-CYCLE":
        return module.PAM(**_pam_with_cycle_terms())
    if contract_type == "STK":
        return module.STK(**_stk_terms())
    if contract_type == "CSH":
        return module.CSH(**_csh_terms())
    if contract_type == "CSH-WITH-INTEREST":
        return module.CSH(**_csh_with_interest_terms())
    raise ValueError(f"unsupported contract_type: {contract_type}")


def _probe_contract(module: Any, contract_type: str) -> dict[str, object]:
    print(f"===== {contract_type} PROBE =====")

    contract = None
    construction_error = None
    try:
        contract = _construct_contract(module, contract_type)
    except Exception as exc:
        construction_error = _format_error(exc)
    print(f"Construction: {_status(contract is not None, construction_error)}")

    portfolio = None
    portfolio_error = None
    if contract is not None:
        try:
            portfolio = module.Portfolio([contract])
        except Exception as exc:
            portfolio_error = _format_error(exc)
    else:
        portfolio_error = "contract construction failed"
    print(f"Portfolio:    {_status(portfolio is not None, portfolio_error)}")

    events_obj = None
    service_error = None
    if portfolio is not None:
        try:
            service = module.PublicActusService()
            server_url = getattr(service, "serverURL", None)
            if server_url is not None:
                print(f"Service URL:  {server_url}")
            events_obj = service.generateEvents(portfolio=portfolio)
        except Exception as exc:
            service_error = _format_error(exc)
    else:
        service_error = "portfolio construction failed"
    print(f"Service call: {_status(events_obj is not None, service_error)}")

    records = _to_records(events_obj) if events_obj is not None else []
    event_types = _event_types(records)
    timestamps = _event_timestamps(records)
    print(f"Event types:  {event_types}")
    print(f"Event times:  {timestamps}")
    print(f"Total events: {len(records)}")

    annual_schedule_confirmed = False
    if contract_type == "STK":
        dv_present = "DV" in event_types
        print(f"DV events present: {'YES' if dv_present else 'NO'}")
    if contract_type == "PAM-WITH-CYCLE":
        event_pairs = [
            (
                str(_first_present(record, ("eventType", "event_type", "type"))),
                str(_first_present(record, ("eventDate", "event_date", "time"))),
            )
            for record in records
        ]
        ip_times = [time for event_type, time in event_pairs if event_type == "IP"]
        annual_schedule_confirmed = (
            len(ip_times) >= 2
            and any(time.startswith("2027") for time in ip_times)
            and any(time.startswith("2028") for time in ip_times)
            and "MD" in event_types
        )
        print(f"Event count:  {len(records)}")
        print(
            "Annual schedule confirmed: "
            f"{'YES' if annual_schedule_confirmed else 'NO'}"
        )
    if contract_type == "CSH-WITH-INTEREST":
        interest_events_present = "IP" in event_types
        print(f"Event count:  {len(records)}")
        print(
            "Interest events present: "
            f"{'YES' if interest_events_present else 'NO'}"
        )

    mapping_error = None
    mapping_ok = False
    if events_obj is not None:
        try:
            aal_events_to_cashflow_dataframe(events_obj)
            mapping_ok = True
        except Exception as exc:
            mapping_error = _format_error(exc)
    else:
        mapping_error = "service call failed"
    print(f"Schema mapping: {_status(mapping_ok, mapping_error)}")
    _print_sample_events(records)
    print()

    return {
        "construction_ok": contract is not None,
        "portfolio_ok": portfolio is not None,
        "service_ok": events_obj is not None,
        "mapping_ok": mapping_ok,
        "event_types": event_types,
        "annual_schedule_confirmed": annual_schedule_confirmed,
    }


def _summary_value(contract_type: str, result: dict[str, object]) -> str:
    ok = bool(result["construction_ok"] and result["portfolio_ok"] and result["service_ok"])
    if contract_type == "STK":
        if not ok:
            return "failed"
        return "ok-with-DV" if "DV" in result["event_types"] else "ok-without-DV"
    if contract_type == "PAM-WITH-CYCLE":
        if not ok:
            return "failed"
        return "ok-with-annual-IP" if bool(result["annual_schedule_confirmed"]) else "ok-without-annual-IP"
    if contract_type == "CSH-WITH-INTEREST":
        if not ok:
            return "failed"
        return "ok-with-IP" if "IP" in result["event_types"] else "ok-without-IP"
    return "ok" if ok else "failed"


def main() -> int:
    try:
        module = get_aal_module()
    except ImportError as exc:
        print("ERROR: AAL is not installed locally; live ACTUS probe cannot run.")
        print(f"Original error: {exc}")
        print("No fallback path was attempted.")
        print(
            "SUMMARY: PAM=failed, STK=failed, CSH=failed, "
            "PAM-WITH-CYCLE=failed, CSH-WITH-INTEREST=failed"
        )
        return 1

    results = {
        contract_type: _probe_contract(module, contract_type)
        for contract_type in (
            "PAM",
            "STK",
            "CSH",
            "PAM-WITH-CYCLE",
            "CSH-WITH-INTEREST",
        )
    }
    print(
        "SUMMARY: "
        f"PAM={_summary_value('PAM', results['PAM'])}, "
        f"STK={_summary_value('STK', results['STK'])}, "
        f"CSH={_summary_value('CSH', results['CSH'])}, "
        f"PAM-WITH-CYCLE={_summary_value('PAM-WITH-CYCLE', results['PAM-WITH-CYCLE'])}, "
        f"CSH-WITH-INTEREST={_summary_value('CSH-WITH-INTEREST', results['CSH-WITH-INTEREST'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
