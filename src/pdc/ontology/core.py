"""Valueflows core entities.

Agents, resources, processes, and recipes, mapped from Valueflows v1.0.0. See
docs/ontology.md for the full mapping.

Everything here is frozen and hashable. The simulation kernel treats worlds as
immutable values so that branching is cheap and results are reproducible
(D-005); mutable ontology objects would defeat that immediately.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pint

from pdc.ontology.actions import Action
from pdc.ontology.citation import Citation

AgentKind = Literal["person", "household", "collective", "commune", "region", "ecosystem"]


@dataclass(frozen=True, slots=True)
class Agent:
    """A Valueflows Agent.

    People, households, farms, workshops, communes, valleys, regions — and
    ecosystems. VF explicitly sanctions treating a soil body or an aquifer as
    an agent that provides and receives resources, which is how phosphorus
    drawdown is modelled here without a special case.

    ``member_of`` gives the recursive nesting of D-009: households nest in
    communes nest in valleys, and every aggregate query walks this. Federation
    is aggregation at a different depth of this tree, not a separate system.
    """

    id: str
    name: str
    kind: AgentKind
    member_of: str | None = None
    attributes: tuple[tuple[str, float], ...] = field(default_factory=tuple)
    """Attributes need standards read from: population, climate normals, and
    so on. A tuple of pairs rather than a dict so the agent stays hashable and
    iteration order is deterministic.

    Sorted on construction. Access via ``attribute()``.
    """

    def __post_init__(self) -> None:
        # Deterministic ordering matters: an unordered structure feeding
        # computation is exactly the class of bug the determinism guarantee
        # exists to prevent.
        object.__setattr__(self, "attributes", tuple(sorted(self.attributes)))

    def attribute(self, path: str) -> float:
        """Read an attribute, raising loudly when it is absent.

        Never returns a default. A silent zero in a needs calculation is the
        worst available failure mode (D-006).
        """
        for key, value in self.attributes:
            if key == path:
                return value
        available = ", ".join(key for key, _ in self.attributes) or "(none)"
        raise KeyError(f"agent {self.id!r} has no attribute {path!r}; has: {available}")

    def has_attribute(self, path: str) -> bool:
        return any(key == path for key, _ in self.attributes)


@dataclass(frozen=True, slots=True)
class ResourceSpecification:
    """The *kind* of a thing: wheat grain, elemental phosphorus, nursing hours.

    Valueflows ResourceSpecification.
    """

    id: str
    name: str
    unit: str
    """Canonical unit for quantities of this specification, as a PDC registry
    unit name. Substance-aware: 'kgP' and 'kgP2O5' are different units and do
    not add."""

    is_labour: bool = False
    """True for skill specifications used by `work` flows. Labour is an effort
    typed by skill, not a resource in inventory."""

    is_ecosystem_stock: bool = False
    """True for stocks held by ecosystem agents — soil phosphorus, aquifer
    volume. Modelled with the same primitives as a granary, flagged only so
    reports can distinguish depletion from consumption."""


@dataclass(frozen=True, slots=True)
class EconomicResource:
    """An actual accountable quantity, somewhere, held by someone.

    Valueflows EconomicResource.
    """

    id: str
    specification_id: str
    custodian_id: str
    quantity: pint.Quantity


@dataclass(frozen=True, slots=True)
class ProcessSpecification:
    """The *kind* of a transformation: milling, sowing, lactation."""

    id: str
    name: str


@dataclass(frozen=True, slots=True)
class RecipeFlow:
    """One input or output of a recipe process, per unit of recipe batch.

    Valueflows RecipeFlow. This is where coefficients live, and therefore
    where public auditability bites hardest: 'why does your farm claim ten
    times the labour' is answered by diffing these.
    """

    action: Action
    specification_id: str
    quantity: pint.Quantity
    citation: Citation
    lag_periods: int = 0
    """Periods between the process running and this flow taking effect.

    Non-zero on outputs whose availability is delayed: alfalfa sown this
    season feeds cattle next season. Lags are the reason a single-period model
    cannot answer the reference question (docs/architecture.md section 4.1).
    """


@dataclass(frozen=True, slots=True)
class RecipeProcess:
    """A reusable definition of how something is made.

    Valueflows RecipeProcess. Batch-sized at the lowest natural quantity and
    scaled when planning, per VF guidance.
    """

    id: str
    name: str
    process_specification_id: str
    inputs: tuple[RecipeFlow, ...]
    outputs: tuple[RecipeFlow, ...]
    duration_periods: int = 1

    def flows(self) -> tuple[RecipeFlow, ...]:
        return self.inputs + self.outputs

    @property
    def is_joint_production(self) -> bool:
        """True when more than one output is produced.

        Joint production is where cost attribution becomes a value judgement,
        so it must never be resolved by a default rule (docs/ontology.md
        section 2.2).
        """
        produced = [f for f in self.outputs if f.action is Action.PRODUCE]
        return len(produced) > 1
