"""Pass/fail invariants on a :class:`BVGEngineResult`.

Implements a focused subset of the validation checklist from the refactor
plan. More checks (mortality bound, formula vs cashflow PV) can be added
on top of :mod:`pk_alm.bvg_liability_engine.pension_logic.valuation_runoff`.
"""

from __future__ import annotations

import pandas as pd

from pk_alm.bvg_liability_engine.orchestration.result import BVGEngineResult
from pk_alm.cashflows.event_types import EX, EXPECTED_PAYOFF_SIGNS
from pk_alm.cashflows.schema import validate_cashflow_dataframe


def _row(name: str, status: str, observed: object, expected: object, note: str = "") -> dict[str, object]:
    return {
        "check_name": name,
        "status": status,
        "observed": observed,
        "expected": expected,
        "notes": note,
    }


def build_validation_report(result: BVGEngineResult) -> pd.DataFrame:
    """Return a check_name / status / observed / expected / notes table."""
    if not isinstance(result, BVGEngineResult):
        raise TypeError(
            f"result must be BVGEngineResult, got {type(result).__name__}"
        )
    rows: list[dict[str, object]] = []

    try:
        validate_cashflow_dataframe(result.cashflows, check_event_type_signs=True)
        rows.append(_row("cashflow_schema_valid", "ok", "valid", "valid"))
    except (ValueError, TypeError) as exc:
        rows.append(_row("cashflow_schema_valid", "fail", str(exc), "valid"))

    sources = set(result.cashflows["source"]) if not result.cashflows.empty else set()
    if sources <= {"BVG"}:
        rows.append(_row("source_is_bvg_only", "ok", sorted(sources), ["BVG"]))
    else:
        rows.append(_row("source_is_bvg_only", "fail", sorted(sources), ["BVG"]))

    bad_signs = []
    for _, row in result.cashflows.iterrows():
        rule = EXPECTED_PAYOFF_SIGNS.get(row["type"])
        if rule == "non_negative" and row["payoff"] < 0:
            bad_signs.append(row["type"])
        if rule == "non_positive" and row["payoff"] > 0:
            bad_signs.append(row["type"])
    rows.append(
        _row(
            "payoff_signs_match_event_type",
            "ok" if not bad_signs else "fail",
            sorted(set(bad_signs)),
            [],
        )
    )

    counts_ok = all(
        s.member_count_total == s.active_count_total + s.retired_count_total
        for s in result.portfolio_states
    )
    rows.append(
        _row(
            "member_counts_consistent",
            "ok" if counts_ok else "fail",
            counts_ok,
            True,
        )
    )

    capital_non_negative = all(
        s.total_capital >= 0 for s in result.portfolio_states
    )
    rows.append(
        _row(
            "capital_non_negative",
            "ok" if capital_non_negative else "fail",
            capital_non_negative,
            True,
        )
    )

    cohort_ids = [c.cohort_id for s in result.portfolio_states for c in s.active_cohorts] + [
        c.cohort_id for s in result.portfolio_states for c in s.retired_cohorts
    ]
    duplicates = pd.Series(cohort_ids).value_counts()
    duplicate_ids = duplicates[duplicates > 1].index.tolist()
    rows.append(
        _row(
            "cohort_ids_unique_per_state",
            "ok" if not duplicate_ids else "warn",
            duplicate_ids,
            [],
            "Across states cohort IDs may repeat by design",
        )
    )

    ex_total = float(
        result.cashflows.loc[result.cashflows["type"] == EX, "payoff"].sum()
    )
    rows.append(
        _row(
            "ex_payoffs_non_positive_sum",
            "ok" if ex_total <= 0 else "fail",
            ex_total,
            "<= 0",
        )
    )

    return pd.DataFrame(
        rows, columns=["check_name", "status", "observed", "expected", "notes"]
    )
