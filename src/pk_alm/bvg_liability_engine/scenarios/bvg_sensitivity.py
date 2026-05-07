"""Small BVG assumption transformers for sensitivity scenarios."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from pk_alm.bvg_liability_engine.assumptions import (
    BVGAssumptions,
    EntryAssumptions,
    MortalityAssumptions,
    RateCurve,
)
from pk_alm.bvg_liability_engine.assumptions.rate_curves import (
    from_dynamic_parameter,
)
from pk_alm.bvg_liability_engine.population_dynamics.entry_policies import (
    FixedEntryPolicy,
    NoEntryPolicy,
    ReplacementEntryPolicy,
)

RateInput = float | Sequence[float] | RateCurve


def closed_fund(assumptions: BVGAssumptions) -> BVGAssumptions:
    """Return assumptions with no new entrants."""
    return replace(assumptions, entry_policy=NoEntryPolicy())


def fixed_entry(
    assumptions: BVGAssumptions,
    entry_assumptions: EntryAssumptions | None = None,
) -> BVGAssumptions:
    """Return assumptions with a fixed-entry policy."""
    entry = entry_assumptions if entry_assumptions is not None else EntryAssumptions()
    return replace(assumptions, entry_policy=FixedEntryPolicy(entry))


def replacement_entry(
    assumptions: BVGAssumptions,
    *,
    template: EntryAssumptions | None = None,
    replacement_ratio: float = 1.0,
) -> BVGAssumptions:
    """Return assumptions with replacement entries for exits and retirements."""
    entry_template = template if template is not None else EntryAssumptions()
    return replace(
        assumptions,
        entry_policy=ReplacementEntryPolicy(
            template=entry_template,
            replacement_ratio=replacement_ratio,
        ),
    )


def conversion_rate_sensitivity(
    assumptions: BVGAssumptions,
    conversion_rate: RateInput,
) -> BVGAssumptions:
    """Return assumptions with a different conversion-rate curve."""
    return replace(
        assumptions,
        conversion_rate=_as_curve(conversion_rate, assumptions=assumptions),
    )


def technical_rate_sensitivity(
    assumptions: BVGAssumptions,
    technical_rate: RateInput,
) -> BVGAssumptions:
    """Return assumptions with a different technical discount-rate curve."""
    return replace(
        assumptions,
        technical_discount_rate=_as_curve(technical_rate, assumptions=assumptions),
    )


def economic_rate_sensitivity(
    assumptions: BVGAssumptions,
    economic_rate: RateInput,
) -> BVGAssumptions:
    """Return assumptions with a different economic discount-rate curve."""
    return replace(
        assumptions,
        economic_discount_rate=_as_curve(economic_rate, assumptions=assumptions),
    )


def mortality_off(assumptions: BVGAssumptions) -> BVGAssumptions:
    """Return assumptions with mortality disabled."""
    return replace(assumptions, mortality=MortalityAssumptions(mode="off"))


def mortality_on(
    assumptions: BVGAssumptions,
    *,
    table_id: str | None = None,
) -> BVGAssumptions:
    """Return assumptions with bundled EK0105 mortality enabled."""
    kwargs = {"mode": "ek0105"}
    if table_id is not None:
        kwargs["table_id"] = table_id
    return replace(assumptions, mortality=MortalityAssumptions(**kwargs))


def active_crediting_rate_sensitivity(
    assumptions: BVGAssumptions,
    active_crediting_rate: RateInput,
) -> BVGAssumptions:
    """Return assumptions with a different active crediting-rate curve."""
    return replace(
        assumptions,
        active_crediting_rate=_as_curve(
            active_crediting_rate,
            assumptions=assumptions,
        ),
    )


def _as_curve(value: RateInput, *, assumptions: BVGAssumptions) -> RateCurve:
    if isinstance(value, RateCurve):
        return value
    return from_dynamic_parameter(
        value,
        start_year=assumptions.start_year,
        horizon_years=max(assumptions.horizon_years, 1),
    )


__all__ = [
    "active_crediting_rate_sensitivity",
    "closed_fund",
    "conversion_rate_sensitivity",
    "economic_rate_sensitivity",
    "fixed_entry",
    "mortality_off",
    "mortality_on",
    "replacement_entry",
    "technical_rate_sensitivity",
]
