"""Cashflow event-type constants and sign rules.

Liability-side BVG events:
- ``PR``: contribution / savings credit inflow (positive payoff).
- ``RP``: retirement pension payment (non-positive payoff).
- ``KA``: capital withdrawal at retirement (non-positive payoff).
- ``EX``: vested-benefit exit payment on turnover (non-positive payoff).
- ``IN``: entry transfer-in capital (non-negative payoff).

Asset-side ACTUS events:
- ``IP``: interest payment (any sign).
- ``MD``: maturity redemption (any sign).
- ``TD``: termination / divestment (any sign).
"""

from __future__ import annotations

from typing import Final, Literal


PR: Final[str] = "PR"
RP: Final[str] = "RP"
KA: Final[str] = "KA"
EX: Final[str] = "EX"
IN: Final[str] = "IN"

IP: Final[str] = "IP"
MD: Final[str] = "MD"
TD: Final[str] = "TD"


BVG_EVENT_TYPES: Final[dict[str, str]] = {
    PR: "Contribution / savings credit inflow",
    RP: "Retirement pension payment",
    KA: "Capital withdrawal at retirement",
    EX: "Exit / vested benefit payment",
    IN: "Entry transfer-in capital",
}

ACTUS_EVENT_TYPES: Final[dict[str, str]] = {
    IP: "Interest payment",
    MD: "Maturity redemption",
    TD: "Termination / divestment",
}

SignRule = Literal["non_negative", "non_positive", "any"]

EXPECTED_PAYOFF_SIGNS: Final[dict[str, SignRule]] = {
    PR: "non_negative",
    RP: "non_positive",
    KA: "non_positive",
    EX: "non_positive",
    IN: "non_negative",
    IP: "any",
    MD: "any",
    TD: "any",
}


def is_known_event_type(event_type: str) -> bool:
    return event_type in EXPECTED_PAYOFF_SIGNS


def expected_sign(event_type: str) -> SignRule:
    return EXPECTED_PAYOFF_SIGNS.get(event_type, "any")
