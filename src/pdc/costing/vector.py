"""The dimensional cost vector.

This is the replacement for Valueflows' value rollup, which requires
converting every input into a single unit — money, or labour-hours, or credits
(D-003). A CostVector carries what a thing cost as a set of physically
distinct quantities and never collapses them.

The rule from D-002, restated because everything here enforces it:

    Aggregate freely WITHIN a dimension. Never reduce ACROSS dimensions.

Adding two cost vectors sums matching components — that is arithmetic inside
one unit and is legal. There is no operation that produces a single number,
and the usual accidental routes to one (``float()``, ``sum()``, ``len()``
arithmetic) raise instead of quietly doing something.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field, replace

import pint


class ScalarReductionError(TypeError):
    """Raised when something tries to collapse a cost vector to one number.

    Not a limitation to be worked around. The information that would be lost
    is the whole point of carrying the vector.
    """


class JointCostError(ValueError):
    """Raised when jointly-borne costs would be double counted."""


@dataclass(frozen=True, slots=True)
class AttributionRecord:
    """A note that some rule was applied at some process.

    Carried on every result so that a cost vector always answers "under what
    assumption?" alongside "how much?".
    """

    process_id: str
    rule_name: str


@dataclass(frozen=True, slots=True)
class CostVector:
    """What something cost, in physically distinct quantities.

    Components are keyed by ResourceSpecification id and held sorted, because
    determinism forbids order-dependent floating-point accumulation (D-005).
    """

    components: tuple[tuple[str, pint.Quantity], ...] = ()
    attributions: tuple[AttributionRecord, ...] = ()
    joint_groups: frozenset[str] = field(default_factory=frozenset)
    """Joint-production groups this cost is borne within.

    When outputs share a cost that nobody has agreed how to split, the honest
    representation is that each output carries the whole of it *jointly*
    (docs/ontology.md section 2.2). Two vectors from the same joint group
    cannot be added, because their costs are the same physical inputs counted
    once, not twice.
    """

    def __post_init__(self) -> None:
        object.__setattr__(self, "components", tuple(sorted(self.components, key=_key)))
        object.__setattr__(self, "attributions", tuple(sorted(self.attributions, key=_record_key)))

    # -- construction ------------------------------------------------------

    @classmethod
    def of(cls, mapping: Mapping[str, pint.Quantity]) -> CostVector:
        return cls(components=tuple(mapping.items()))

    @classmethod
    def single(cls, specification_id: str, quantity: pint.Quantity) -> CostVector:
        return cls(components=((specification_id, quantity),))

    # -- inspection --------------------------------------------------------

    def component(self, specification_id: str) -> pint.Quantity | None:
        """One component, or None. Never a zero of unknown unit: a component
        that is absent is different from one that is zero, and inventing a
        unit for the absent case is how silent errors start."""
        for key, value in self.components:
            if key == specification_id:
                return value
        return None

    def require(self, specification_id: str) -> pint.Quantity:
        """One component, raising if it is absent.

        The assertive counterpart to ``component()``, matching the
        ``attribute()`` / ``has_attribute()`` pair on Agent: code that knows a
        component should be there says so, and fails loudly when it is not,
        rather than propagating a None into arithmetic.
        """
        value = self.component(specification_id)
        if value is None:
            present = ", ".join(self.specifications()) or "(none)"
            raise KeyError(f"cost vector has no component {specification_id!r}; has: {present}")
        return value

    def specifications(self) -> tuple[str, ...]:
        return tuple(key for key, _ in self.components)

    def __iter__(self) -> Iterator[tuple[str, pint.Quantity]]:
        return iter(self.components)

    def __len__(self) -> int:
        return len(self.components)

    def __bool__(self) -> bool:
        return bool(self.components)

    # -- arithmetic within dimensions -------------------------------------

    def __add__(self, other: CostVector) -> CostVector:
        if not isinstance(other, CostVector):
            return NotImplemented

        overlap = self.joint_groups & other.joint_groups
        if overlap:
            raise JointCostError(
                f"refusing to add cost vectors that share joint-production "
                f"group(s) {sorted(overlap)}: these carry the same physical "
                f"inputs, so summing them double counts. Attribute the joint "
                f"cost with a named rule first, or keep the outputs separate."
            )

        merged: dict[str, pint.Quantity] = dict(self.components)
        for key, value in other.components:
            existing = merged.get(key)
            # pint raises if the units are incompatible, which is the guard
            # doing its job: two components sharing a key must share a unit.
            merged[key] = value if existing is None else existing + value

        return CostVector(
            components=tuple(merged.items()),
            attributions=tuple({*self.attributions, *other.attributions}),
            joint_groups=self.joint_groups | other.joint_groups,
        )

    def scaled(self, factor: float | pint.Quantity) -> CostVector:
        """Scale every component. Used when a recipe batch is scaled."""
        return replace(
            self, components=tuple((key, value * factor) for key, value in self.components)
        )

    def with_attribution(self, record: AttributionRecord) -> CostVector:
        return replace(self, attributions=(*self.attributions, record))

    def in_joint_group(self, group_id: str) -> CostVector:
        return replace(self, joint_groups=self.joint_groups | {group_id})

    # -- the reductions that must not exist --------------------------------

    def __float__(self) -> float:
        raise ScalarReductionError(_REFUSAL)

    def __int__(self) -> int:
        raise ScalarReductionError(_REFUSAL)

    def __lt__(self, other: object) -> bool:
        raise ScalarReductionError(
            "cost vectors are not ordered. Most pairs are genuinely "
            "incomparable — one is cheaper in phosphorus and dearer in "
            "labour — and picking a winner requires an exchange rate this "
            "project refuses to have (D-001, D-002). Compare components, or "
            "use analysis.frontier() for the non-dominated set."
        )

    __le__ = __lt__
    __gt__ = __lt__
    __ge__ = __lt__

    def __str__(self) -> str:
        if not self.components:
            return "CostVector(empty)"
        body = ", ".join(f"{key}={value:~P}" for key, value in self.components)
        return f"CostVector({body})"


_REFUSAL = (
    "a CostVector cannot be reduced to a single number. Summing kilograms of "
    "phosphorus with labour-hours requires an exchange rate between them, and "
    "choosing one is a political act rather than an arithmetic one (D-002). "
    "Read the component you want with .component(spec_id), or report the "
    "whole vector."
)


def _key(item: tuple[str, pint.Quantity]) -> str:
    return item[0]


def _record_key(record: AttributionRecord) -> tuple[str, str]:
    return (record.process_id, record.rule_name)
