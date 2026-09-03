"""Dimensional rollup through the recipe graph.

Walks backwards from a wanted output to the primary inputs that produced it,
accumulating a CostVector. This is Valueflows' rollup with the scalarization
removed (D-003): same traversal, but the result stays a vector of physically
distinct quantities instead of collapsing into money or hours.

A specification with no recipe producing it is *primary*: soil phosphorus,
water, land, labour. Those terminate the walk and become components.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pint

from pdc.costing.attribution import AttributionRule
from pdc.costing.vector import AttributionRecord, CostVector
from pdc.ontology import Action, RecipeProcess

COSTED_ACTIONS = frozenset({Action.CONSUME, Action.USE, Action.WORK})
"""Input actions that contribute to cost.

`consume` and `use` draw on resources; `work` draws on people's time. `cite`
is deliberately excluded: citing a design or a technique uses nothing up, and
charging for knowledge is how enclosure starts.
"""


class CircularProductionError(ValueError):
    """Raised when the recipe graph has a production cycle.

    Real agricultural systems have these — manure to soil to alfalfa to cattle
    to manure — and they are not an error in the world, only in this
    traversal. Resolving them needs a fixed-point solve rather than a walk,
    which arrives with forward propagation (M4). Until then, saying so plainly
    beats looping or silently truncating.
    """


class NoAttributionRuleError(ValueError):
    """Raised when joint production is met with no rule supplied.

    Deliberately not defaulted. Silently allocating by mass would be exactly
    the reduction D-002 forbids, hidden one layer down where nobody audits it.
    """


@dataclass(frozen=True, slots=True)
class RollupResult:
    """A cost vector plus what it cost it of."""

    specification_id: str
    quantity: pint.Quantity
    cost: CostVector

    def __str__(self) -> str:
        return f"{self.quantity:~P} of {self.specification_id}: {self.cost}"


def _producers(recipes: Sequence[RecipeProcess]) -> dict[str, list[RecipeProcess]]:
    index: dict[str, list[RecipeProcess]] = {}
    for recipe in sorted(recipes, key=lambda r: r.id):
        for flow in recipe.outputs:
            if flow.action is Action.PRODUCE:
                index.setdefault(flow.specification_id, []).append(recipe)
    return index


def rollup(
    specification_id: str,
    quantity: pint.Quantity,
    recipes: Sequence[RecipeProcess],
    *,
    attribution: AttributionRule | None = None,
    _visiting: tuple[str, ...] = (),
    _producers_index: dict[str, list[RecipeProcess]] | None = None,
) -> RollupResult:
    """Roll a quantity of one specification back to its primary inputs.

    ``attribution`` is required only if a joint-producing recipe is reached.
    """
    index = _producers_index if _producers_index is not None else _producers(recipes)

    if specification_id in _visiting:
        cycle = " -> ".join((*_visiting, specification_id))
        raise CircularProductionError(
            f"production cycle in the recipe graph: {cycle}. Cycles are real "
            "in agriculture and are resolved by a fixed-point solve in forward "
            "propagation, not by this backward walk."
        )

    candidates = index.get(specification_id, [])
    if not candidates:
        # Primary input: nothing produces it, so the walk terminates here.
        return RollupResult(
            specification_id, quantity, CostVector.single(specification_id, quantity)
        )

    if len(candidates) > 1:
        raise NoAttributionRuleError(
            f"{len(candidates)} recipes produce {specification_id!r} "
            f"({', '.join(r.id for r in candidates)}). Choosing between "
            "production routes is a decision for people, not for a rollup "
            "(D-001). Pass a recipe set with one route, or roll each up "
            "separately and show both."
        )

    recipe = candidates[0]
    output = next(
        flow
        for flow in recipe.outputs
        if flow.action is Action.PRODUCE and flow.specification_id == specification_id
    )

    scale = (quantity / output.quantity).to("dimensionless").magnitude

    share = 1.0
    joint_group: str | None = None
    if recipe.is_joint_production:
        if attribution is None:
            produced = [f.specification_id for f in recipe.outputs if f.action is Action.PRODUCE]
            raise NoAttributionRuleError(
                f"{recipe.id!r} jointly produces {sorted(produced)} and no attribution "
                "rule was supplied. Every way of dividing a joint cost is a value "
                "judgement, so PDC will not pick one for you (docs/ontology.md 2.2). "
                "Pass ExplicitShares, SingleOutput, ProportionalToOutput, or "
                "Unattributed."
            )
        shares = attribution.shares(recipe)
        if shares is None:
            joint_group = f"{recipe.id}:joint"
        else:
            share = shares[specification_id]

    total = CostVector()
    for flow in recipe.inputs:
        if flow.action not in COSTED_ACTIONS:
            continue
        contribution = rollup(
            flow.specification_id,
            flow.quantity,
            recipes,
            attribution=attribution,
            _visiting=(*_visiting, specification_id),
            _producers_index=index,
        ).cost
        total = total + contribution

    total = total.scaled(scale * share)

    if recipe.is_joint_production and attribution is not None:
        total = total.with_attribution(AttributionRecord(recipe.id, attribution.name))
        if joint_group is not None:
            total = total.in_joint_group(joint_group)

    return RollupResult(specification_id, quantity, total)
