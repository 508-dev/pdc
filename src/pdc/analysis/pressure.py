"""How hard a scarce resource is being asked to work.

Gap analysis, per D-004: report which constraint binds and by how much, in its
own units. There is no score here and no ranking of the options — only what is
available and what each way of using it would take.

This lives in the kernel rather than in a renderer because two shells now need
it, and analysis computed in a presentation layer is how the screen starts
disagreeing with the model (D-010).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import pint

from pdc.ontology import Action, RecipeProcess


@dataclass(frozen=True, slots=True)
class Demand:
    """What one way of using a resource would take."""

    recipe_id: str
    recipe_name: str
    per_batch: pint.Quantity
    batches: float
    total: pint.Quantity

    def ratio_of(self, available: pint.Quantity) -> float:
        """Multiples of the available stock this demand represents."""
        if available.magnitude == 0:
            return float("inf")
        return (self.total / available).to("dimensionless").magnitude

    def satisfiable_batches(self, available: pint.Quantity) -> float:
        """How many batches the available stock would actually support."""
        if self.per_batch.magnitude <= 0:
            return self.batches
        return (available / self.per_batch).to("dimensionless").magnitude


@dataclass(frozen=True, slots=True)
class ResourcePressure:
    """One scarce resource, and every claim on it."""

    specification_id: str
    available: pint.Quantity
    demands: tuple[Demand, ...]

    @property
    def total_demanded(self) -> pint.Quantity | None:
        """Sum of all claims. Aggregation within one dimension, so legal."""
        running: pint.Quantity | None = None
        for demand in self.demands:
            running = demand.total if running is None else running + demand.total
        return running

    @property
    def is_scarce(self) -> bool:
        total = self.total_demanded
        return total is not None and bool(total > self.available)


def resource_pressure(
    specification_id: str,
    available: pint.Quantity,
    recipes: Sequence[RecipeProcess],
    batches: Mapping[str, float],
) -> ResourcePressure:
    """What each planned use of a resource would take, against what there is.

    ``batches`` maps recipe id to intended scale. Recipes that do not consume
    the resource are ignored.

    Note what this deliberately does not do: it does not propose a division,
    rank the demands, or identify a "best" use. Those are decisions (D-001).
    """
    demands: list[Demand] = []

    for recipe in sorted(recipes, key=lambda r: r.id):
        scale = batches.get(recipe.id)
        if not scale:
            continue
        for flow in recipe.inputs:
            if flow.action is not Action.CONSUME:
                continue
            if flow.specification_id != specification_id:
                continue
            demands.append(
                Demand(
                    recipe_id=recipe.id,
                    recipe_name=recipe.name,
                    per_batch=flow.quantity,
                    batches=scale,
                    total=flow.quantity * scale,
                )
            )

    return ResourcePressure(specification_id, available, tuple(demands))
