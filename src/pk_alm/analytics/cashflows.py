"""Annual cashflow analytics over the shared cashflow schema.

Aggregates schema-valid cashflows by year and reports the structural
liquidity inflection point. This module is read-only over its inputs:
it does not run engines, project portfolios, or value liabilities.
"""

from __future__ import annotations

import math
import numbers

import pandas as pd

from pk_alm.cashflows.schema import CASHFLOW_COLUMNS, validate_cashflow_dataframe

ANNUAL_CASHFLOW_COLUMNS = (
    "reporting_year",
    "contribution_cashflow",
    "pension_payment_cashflow",
    "capital_withdrawal_cashflow",
    "other_cashflow",
    "net_cashflow",
    "structural_net_cashflow",
    "cumulative_net_cashflow",
    "cumulative_structural_net_cashflow",
    "currency",
)

_MONETARY_FIELDS = (
    "contribution_cashflow",
    "pension_payment_cashflow",
    "capital_withdrawal_cashflow",
    "other_cashflow",
    "net_cashflow",
    "structural_net_cashflow",
    "cumulative_net_cashflow",
    "cumulative_structural_net_cashflow",
)

_IDENTITY_TOLERANCE = 1e-5


# ---------------------------------------------------------------------------
# Local validation helpers
# ---------------------------------------------------------------------------


def _validate_non_bool_int(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, int):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")
    return value


def _validate_non_bool_real(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be numeric, got {type(value).__name__}")
    fval = float(value)
    if math.isnan(fval):
        raise ValueError(f"{name} must not be NaN")
    return fval


# ---------------------------------------------------------------------------
# summarize_cashflows_by_year
# ---------------------------------------------------------------------------


def summarize_cashflows_by_year(cashflows: pd.DataFrame) -> pd.DataFrame:
    """Aggregate schema-valid cashflows into one row per reporting year.

    Cashflow buckets:
      contribution_cashflow      -> sum of payoff where type == "PR"
      pension_payment_cashflow   -> sum of payoff where type == "RP"
      capital_withdrawal_cashflow-> sum of payoff where type == "KA"
      other_cashflow             -> sum of payoff for all other types
    Derived series:
      net_cashflow                          = sum of all payoffs
      structural_net_cashflow               = contribution + pension_payment
                                              (excludes KA and other)
      cumulative_net_cashflow               = cumulative sum sorted by year
      cumulative_structural_net_cashflow    = cumulative sum sorted by year
    """
    if not isinstance(cashflows, pd.DataFrame):
        raise TypeError(
            f"cashflows must be a pandas DataFrame, got {type(cashflows).__name__}"
        )
    validate_cashflow_dataframe(cashflows)

    if cashflows.empty:
        return pd.DataFrame(columns=list(ANNUAL_CASHFLOW_COLUMNS))

    unique_currencies = cashflows["currency"].unique().tolist()
    if len(unique_currencies) > 1:
        raise ValueError(
            f"only one currency per summary is supported, "
            f"got {sorted(unique_currencies)}"
        )
    currency = unique_currencies[0]

    work = cashflows.copy(deep=True)
    work["reporting_year"] = pd.to_datetime(work["time"]).dt.year.astype(int)

    years = sorted(work["reporting_year"].unique().tolist())
    rows: list[dict[str, object]] = []
    cum_net = 0.0
    cum_struct = 0.0

    for year in years:
        chunk = work[work["reporting_year"] == year]
        contrib = float(chunk.loc[chunk["type"] == "PR", "payoff"].sum())
        pension = float(chunk.loc[chunk["type"] == "RP", "payoff"].sum())
        withdrawal = float(chunk.loc[chunk["type"] == "KA", "payoff"].sum())
        other = float(
            chunk.loc[~chunk["type"].isin(["PR", "RP", "KA"]), "payoff"].sum()
        )

        net = contrib + pension + withdrawal + other
        struct = contrib + pension
        cum_net += net
        cum_struct += struct

        rows.append(
            {
                "reporting_year": int(year),
                "contribution_cashflow": contrib,
                "pension_payment_cashflow": pension,
                "capital_withdrawal_cashflow": withdrawal,
                "other_cashflow": other,
                "net_cashflow": net,
                "structural_net_cashflow": struct,
                "cumulative_net_cashflow": cum_net,
                "cumulative_structural_net_cashflow": cum_struct,
                "currency": currency,
            }
        )

    return pd.DataFrame(rows, columns=list(ANNUAL_CASHFLOW_COLUMNS))


# ---------------------------------------------------------------------------
# validate_annual_cashflow_dataframe
# ---------------------------------------------------------------------------


def validate_annual_cashflow_dataframe(df: pd.DataFrame) -> bool:
    if not isinstance(df, pd.DataFrame):
        raise TypeError(
            f"df must be a pandas DataFrame, got {type(df).__name__}"
        )

    missing = [c for c in ANNUAL_CASHFLOW_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")

    if list(df.columns) != list(ANNUAL_CASHFLOW_COLUMNS):
        raise ValueError(
            f"columns must be in order {list(ANNUAL_CASHFLOW_COLUMNS)}, "
            f"got {list(df.columns)}"
        )

    if df.empty:
        return True

    if df[list(ANNUAL_CASHFLOW_COLUMNS)].isna().any().any():
        raise ValueError(
            "required columns must not contain NaN/None/NaT/pd.NA"
        )

    for idx, row in df.iterrows():
        prefix = f"row {idx}"

        # numpy/pandas integer scalar types are not subclasses of `int`,
        # so cast first.
        try:
            year = int(row["reporting_year"])
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"{prefix}: reporting_year must be integer-like, "
                f"got {row['reporting_year']!r}"
            ) from e
        _validate_non_bool_int(year, f"{prefix}: reporting_year")
        if year < 0:
            raise ValueError(f"{prefix}: reporting_year must be >= 0, got {year}")

        for fname in _MONETARY_FIELDS:
            _validate_non_bool_real(row[fname], f"{prefix}: {fname}")

        cur = row["currency"]
        if not isinstance(cur, str) or not cur.strip():
            raise ValueError(f"{prefix}: currency must be a non-empty string")

        net_expected = (
            row["contribution_cashflow"]
            + row["pension_payment_cashflow"]
            + row["capital_withdrawal_cashflow"]
            + row["other_cashflow"]
        )
        if not math.isclose(
            row["net_cashflow"], net_expected, abs_tol=_IDENTITY_TOLERANCE
        ):
            raise ValueError(
                f"{prefix}: net_cashflow must equal contribution + pension + "
                f"withdrawal + other (expected {net_expected}, "
                f"got {row['net_cashflow']})"
            )

        struct_expected = (
            row["contribution_cashflow"] + row["pension_payment_cashflow"]
        )
        if not math.isclose(
            row["structural_net_cashflow"],
            struct_expected,
            abs_tol=_IDENTITY_TOLERANCE,
        ):
            raise ValueError(
                f"{prefix}: structural_net_cashflow must equal contribution + "
                f"pension (expected {struct_expected}, "
                f"got {row['structural_net_cashflow']})"
            )

    return True


# ---------------------------------------------------------------------------
# find_liquidity_inflection_year
# ---------------------------------------------------------------------------


def find_liquidity_inflection_year(
    annual_cashflows: pd.DataFrame,
    *,
    use_structural: bool = True,
) -> int | None:
    """Return the first reporting year where the chosen net cashflow is < 0.

    When use_structural=True, uses structural_net_cashflow (excludes KA / other).
    When use_structural=False, uses net_cashflow.
    Returns None if no negative year exists or the input is empty.
    """
    if not isinstance(use_structural, bool):
        raise TypeError(
            f"use_structural must be bool, got {type(use_structural).__name__}"
        )
    validate_annual_cashflow_dataframe(annual_cashflows)

    if annual_cashflows.empty:
        return None

    column = "structural_net_cashflow" if use_structural else "net_cashflow"
    df_sorted = annual_cashflows.sort_values("reporting_year")
    negatives = df_sorted[df_sorted[column] < 0]
    if negatives.empty:
        return None
    return int(negatives.iloc[0]["reporting_year"])
