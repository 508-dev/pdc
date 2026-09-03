"""Attribution rules for joint production.

A dairy produces milk and manure. A wheat field produces grain and straw. The
phosphorus entering the process has to be divided between the outputs, and
**every possible division is a value judgement** — allocation by mass, by
energy, by what someone considers the "main" product, all encode a view about
what the process is really for.

So PDC never picks one. A rule is a named object supplied by the caller, and
it is recorded on every result, so a cost vector always reports the assumption
that produced it (docs/ontology.md section 2.2).

There is deliberately no default. A rollup that meets joint production with no
rule supplied raises, because silently allocating by mass would be D-002's
failure mode hidden one layer down where nobody audits it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import pint

from pdc.ontology import Action, RecipeProcess


class AttributionError(ValueError):
    """Raised when a rule cannot be applied to a process."""


@runtime_checkable
class AttributionRule(Protocol):
    """Splits a process's costs across its outputs."""

    @property
    def name(self) -> str:
        """Recorded on every result. Must identify the rule unambiguously."""

    def shares(self, recipe: RecipeProcess) -> dict[str, float] | None:
        """Fraction of cost borne by each produced specification.

        Returns None to decline attribution, meaning the cost is borne
        jointly: every output carries the whole of it, and the resulting
        vectors cannot be added together.
        """


def _produced(recipe: RecipeProcess) -> list[tuple[str, pint.Quantity]]:
    return [
        (flow.specification_id, flow.quantity)
        for flow in recipe.outputs
        if flow.action is Action.PRODUCE
    ]


@dataclass(frozen=True, slots=True)
class Unattributed:
    """Decline to split. Each output carries the joint cost in full.

    The honest representation when nobody has agreed a division. It is
    deliberately awkward to work with — vectors from the same joint group
    refuse to be added — because the awkwardness is the information: those
    costs really are one set of inputs, and treating them as two is wrong.
    """

    @property
    def name(self) -> str:
        return "unattributed"

    def shares(self, recipe: RecipeProcess) -> dict[str, float] | None:
        return None


@dataclass(frozen=True, slots=True)
class SingleOutput:
    """Charge everything to one output; the rest are treated as free.

    Appropriate when the other outputs are genuinely incidental to the people
    doing the work — straw left on the field, whey fed back to pigs. It is
    still an assumption, and it is still named.
    """

    specification_id: str

    @property
    def name(self) -> str:
        return f"single-output:{self.specification_id}"

    def shares(self, recipe: RecipeProcess) -> dict[str, float]:
        produced = dict(_produced(recipe))
        if self.specification_id not in produced:
            raise AttributionError(
                f"rule {self.name!r} names an output {self.specification_id!r} "
                f"that {recipe.id!r} does not produce; it produces "
                f"{sorted(produced)}"
            )
        return {spec: (1.0 if spec == self.specification_id else 0.0) for spec in produced}


@dataclass(frozen=True, slots=True)
class ExplicitShares:
    """A hand-specified division, agreed by whoever agreed it.

    The most honest rule available when a division is genuinely a decision:
    it puts the numbers where they can be read and argued with, rather than
    hiding them inside a formula that looks objective.
    """

    shares_by_specification: tuple[tuple[str, float], ...]
    label: str = "explicit"

    @property
    def name(self) -> str:
        return f"explicit:{self.label}"

    def shares(self, recipe: RecipeProcess) -> dict[str, float]:
        mapping = dict(self.shares_by_specification)
        produced = dict(_produced(recipe))

        missing = sorted(set(produced) - set(mapping))
        if missing:
            raise AttributionError(
                f"rule {self.name!r} gives no share for outputs {missing} of {recipe.id!r}; "
                "an unstated share is not the same as a zero one"
            )
        unknown = sorted(set(mapping) - set(produced))
        if unknown:
            raise AttributionError(
                f"rule {self.name!r} gives shares for {unknown}, which {recipe.id!r} "
                "does not produce"
            )
        total = sum(mapping.values())
        if abs(total - 1.0) > 1e-9:
            raise AttributionError(f"rule {self.name!r} shares sum to {total}, not 1.0")
        return mapping


@dataclass(frozen=True, slots=True)
class ProportionalToOutput:
    """Divide in proportion to output quantity.

    Only valid when the outputs are commensurable — two masses on the same
    basis. It refuses rather than guesses when they are not, because dividing
    'in proportion' between 5.5 tonnes of milk and 2 hectares of anything is
    not a computation, it is a category error with a number attached.
    """

    label: str = "proportional-to-output"

    @property
    def name(self) -> str:
        return f"proportional:{self.label}"

    def shares(self, recipe: RecipeProcess) -> dict[str, float]:
        produced = _produced(recipe)
        if not produced:
            raise AttributionError(f"{recipe.id!r} produces nothing to attribute across")

        reference = produced[0][1]
        magnitudes: dict[str, float] = {}
        for specification_id, quantity in produced:
            try:
                magnitudes[specification_id] = quantity.to(reference.units).magnitude
            except pint.DimensionalityError as exc:
                raise AttributionError(
                    f"cannot divide {recipe.id!r} in proportion to output: "
                    f"{specification_id!r} is {quantity.units:~P} and "
                    f"{produced[0][0]!r} is {reference.units:~P}. These are not "
                    "commensurable, so a proportional split is not defined. Use "
                    "ExplicitShares, or Unattributed if no division is agreed."
                ) from exc

        total = sum(magnitudes.values())
        if total <= 0:
            raise AttributionError(f"{recipe.id!r} has no positive output to attribute across")
        return {spec: value / total for spec, value in magnitudes.items()}
