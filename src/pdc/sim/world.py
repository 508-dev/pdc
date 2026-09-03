"""World state, plans, and allocations.

State is immutable: every period produces a new WorldState rather than
mutating one. Branching worlds cheaply is what makes scenario exploration
possible (D-005), and a mutable state defeats that on the first fork.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace

import pint

from pdc.ontology import RecipeProcess

StockKey = tuple[str, str]
"""(custodian agent id, resource specification id)."""


@dataclass(frozen=True, slots=True)
class WorldState:
    """Stocks held, at one period.

    Stocks are keyed by holder and specification and held sorted, because
    determinism forbids order-dependent accumulation (D-005).
    """

    period: int = 0
    stocks: tuple[tuple[StockKey, pint.Quantity], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "stocks", tuple(sorted(self.stocks, key=lambda item: item[0])))

    @classmethod
    def of(cls, period: int, stocks: Mapping[StockKey, pint.Quantity]) -> WorldState:
        return cls(period=period, stocks=tuple(stocks.items()))

    def held(self, custodian_id: str, specification_id: str) -> pint.Quantity | None:
        for (holder, specification), quantity in self.stocks:
            if holder == custodian_id and specification == specification_id:
                return quantity
        return None

    def total(self, specification_id: str) -> pint.Quantity | None:
        """Sum one specification across all holders.

        Aggregation within a dimension, which D-002 permits. There is
        deliberately no method that sums across specifications.
        """
        running: pint.Quantity | None = None
        for (_, specification), quantity in self.stocks:
            if specification == specification_id:
                running = quantity if running is None else running + quantity
        return running

    def with_stocks(self, updates: Mapping[StockKey, pint.Quantity]) -> WorldState:
        merged = dict(self.stocks)
        merged.update(updates)
        return replace(self, stocks=tuple(merged.items()))

    def adjusted(self, key: StockKey, delta: pint.Quantity) -> WorldState:
        current = self.held(*key)
        return self.with_stocks({key: delta if current is None else current + delta})


@dataclass(frozen=True, slots=True)
class ProcessPlan:
    """An intention to run a recipe at some scale.

    An intention, not a promise: forward propagation reports what the plan
    would actually achieve given what is available, which is usually less.
    """

    agent_id: str
    recipe_id: str
    intended_batches: float
    from_period: int = 0
    """First period this plan may run."""

    through_period: int | None = None
    """Last period, or None for every period of the run."""

    def active_in(self, period: int) -> bool:
        if period < self.from_period:
            return False
        return self.through_period is None or period <= self.through_period


@dataclass(frozen=True, slots=True)
class Allocation:
    """How scarce primary resources are divided, per agent, per period.

    This is the assumption a scenario varies, and it is always a human
    decision recorded as input. PDC never computes an allocation: doing so is
    precisely the capability D-001 refuses.
    """

    label: str
    shares: tuple[tuple[StockKey, pint.Quantity], ...] = field(default_factory=tuple)
    """(agent, specification) -> quantity made available per period."""

    def __post_init__(self) -> None:
        object.__setattr__(self, "shares", tuple(sorted(self.shares, key=lambda item: item[0])))

    @classmethod
    def of(cls, label: str, shares: Mapping[StockKey, pint.Quantity]) -> Allocation:
        return cls(label=label, shares=tuple(shares.items()))

    def granted(self, agent_id: str, specification_id: str) -> pint.Quantity | None:
        for (holder, specification), quantity in self.shares:
            if holder == agent_id and specification == specification_id:
                return quantity
        return None

    def total_of(self, specification_id: str) -> pint.Quantity | None:
        running: pint.Quantity | None = None
        for (_, specification), quantity in self.shares:
            if specification == specification_id:
                running = quantity if running is None else running + quantity
        return running


@dataclass(frozen=True, slots=True)
class Scenario:
    """A complete, reproducible question put to the model.

    Serialises to a file someone else runs against their own mirror, which is
    what makes "check my arithmetic" a real invitation rather than a rhetorical
    one (D-005, D-010).
    """

    label: str
    allocation: Allocation
    plans: tuple[ProcessPlan, ...]
    periods: int = 3
    consumption_standard_id: str | None = None
    """Which standard governs how much people actually eat.

    Must be named explicitly. With several standards declared, picking one to
    drive consumption is a choice about what counts as a normal ration, and
    inferring it — by taking the largest, say, or the first — would be PDC
    quietly ranking standards that D-006 holds to be peers.

    None means nothing is consumed and stocks accumulate, which is only
    meaningful for studying production in isolation.
    """

    def plans_for(self, period: int) -> tuple[ProcessPlan, ...]:
        return tuple(
            plan
            for plan in sorted(self.plans, key=lambda p: (p.agent_id, p.recipe_id))
            if plan.active_in(period)
        )


def recipes_by_id(recipes: tuple[RecipeProcess, ...]) -> dict[str, RecipeProcess]:
    return {recipe.id: recipe for recipe in sorted(recipes, key=lambda r: r.id)}
