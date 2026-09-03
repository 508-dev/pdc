"""Branched worlds.

A branch is a scenario derived from a parent by an ordered set of assumptions.
Reality is not a privileged data structure: it is the branch whose events were
authored by people rather than generated (D-005).

Storage is deltas from the parent, not copies. Exploring alternatives spawns
branches in the thousands — "what if we gave the alfalfa farms a third",
"what if the harvest fails", "what if Chakar and Northsetting pool their
grain" — and copying a world per branch dies quickly.

Branches are content addressed: identical assumptions on an identical parent
produce an identical digest. That is what makes "run my scenario and tell me
where you get a different answer" a decidable question.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, replace
from typing import Any

import pint

from pdc.sim.identity import canonical_json, digest, quantity_json
from pdc.sim.world import Allocation, ProcessPlan, Scenario
from pdc.units import ureg


class AssumptionKind(enum.Enum):
    """The kinds of change a branch may make.

    A closed set on purpose. An assumption that cannot be named is one that
    cannot be diffed, and diffing assumptions is how two people find out why
    their models disagree.
    """

    SET_ALLOCATION_SHARE = "set_allocation_share"
    SET_PLAN_SCALE = "set_plan_scale"
    REMOVE_PLAN = "remove_plan"
    SET_PERIODS = "set_periods"
    SET_CONSUMPTION_STANDARD = "set_consumption_standard"


@dataclass(frozen=True, slots=True)
class Assumption:
    """One stated change, with the reason it was made.

    ``rationale`` is not decoration. A branch is an argument, and an argument
    whose premises are unlabelled is hard to contest — which is the failure
    D-010 exists to prevent.
    """

    kind: AssumptionKind
    target: tuple[str, ...]
    value: pint.Quantity | float | str | None = None
    rationale: str = ""

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "kind": self.kind.value,
            "target": list(self.target),
            "rationale": self.rationale,
        }
        if isinstance(self.value, pint.Quantity):
            payload["value"] = quantity_json(self.value)
        else:
            payload["value"] = self.value
        return payload

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> Assumption:
        raw = payload.get("value")
        value: pint.Quantity | float | str | None = (
            ureg.Quantity(raw["magnitude"], raw["units"]) if isinstance(raw, dict) else raw
        )
        return cls(
            kind=AssumptionKind(payload["kind"]),
            target=tuple(payload["target"]),
            value=value,
            rationale=payload.get("rationale", ""),
        )


@dataclass(frozen=True, slots=True)
class Branch:
    """A scenario expressed as deltas from a parent."""

    label: str
    assumptions: tuple[Assumption, ...] = ()
    parent: str | None = None
    """Digest of the parent branch, or None at the root."""

    def to_json(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "parent": self.parent,
            "assumptions": [a.to_json() for a in self.assumptions],
        }

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> Branch:
        return cls(
            label=payload["label"],
            assumptions=tuple(Assumption.from_json(a) for a in payload["assumptions"]),
            parent=payload.get("parent"),
        )

    @property
    def digest(self) -> str:
        """Content address over parent and assumptions.

        The label is excluded: two branches that make the same changes to the
        same parent are the same branch, whatever anyone called them.
        """
        return digest(
            {
                "parent": self.parent,
                "assumptions": [a.to_json() for a in self.assumptions],
            }
        )

    def fork(self, label: str, *assumptions: Assumption) -> Branch:
        """A child branch adding further assumptions."""
        return Branch(label=label, assumptions=assumptions, parent=self.digest)

    def diff(self, other: Branch) -> tuple[str, ...]:
        """Assumptions present in one branch and not the other.

        The workflow this exists for: two communities disagree about an
        outcome, so they compare the premises rather than the conclusions.
        """
        mine = {canonical_json(a.to_json()): a for a in self.assumptions}
        theirs = {canonical_json(a.to_json()): a for a in other.assumptions}
        lines = []
        for key in sorted(set(mine) - set(theirs)):
            lines.append(f"- only in {self.label}: {_describe(mine[key])}")
        for key in sorted(set(theirs) - set(mine)):
            lines.append(f"- only in {other.label}: {_describe(theirs[key])}")
        return tuple(lines)


def _describe(assumption: Assumption) -> str:
    target = "/".join(assumption.target)
    value = assumption.value
    rendered = f"{value:~P}" if isinstance(value, pint.Quantity) else value
    text = f"{assumption.kind.value} {target} = {rendered}"
    return f"{text} ({assumption.rationale})" if assumption.rationale else text


def apply_branch(base: Scenario, branch: Branch) -> Scenario:
    """Derive a scenario by applying a branch's assumptions in order.

    Pure: the base is untouched, which is what makes branching cheap and
    exploration safe.
    """
    scenario = base

    for assumption in branch.assumptions:
        match assumption.kind:
            case AssumptionKind.SET_ALLOCATION_SHARE:
                agent_id, specification_id = assumption.target
                if not isinstance(assumption.value, pint.Quantity):
                    raise ValueError("an allocation share must be a quantity")
                shares = dict(scenario.allocation.shares)
                shares[(agent_id, specification_id)] = assumption.value
                scenario = replace(
                    scenario,
                    allocation=Allocation(
                        label=f"{scenario.allocation.label}+{branch.label}",
                        shares=tuple(shares.items()),
                    ),
                )

            case AssumptionKind.SET_PLAN_SCALE:
                agent_id, recipe_id = assumption.target
                scenario = replace(
                    scenario,
                    plans=tuple(
                        replace(plan, intended_batches=float(assumption.value))  # type: ignore[arg-type]
                        if plan.agent_id == agent_id and plan.recipe_id == recipe_id
                        else plan
                        for plan in scenario.plans
                    ),
                )

            case AssumptionKind.REMOVE_PLAN:
                agent_id, recipe_id = assumption.target
                scenario = replace(
                    scenario,
                    plans=tuple(
                        plan
                        for plan in scenario.plans
                        if not (plan.agent_id == agent_id and plan.recipe_id == recipe_id)
                    ),
                )

            case AssumptionKind.SET_PERIODS:
                scenario = replace(scenario, periods=int(assumption.value))  # type: ignore[arg-type]

            case AssumptionKind.SET_CONSUMPTION_STANDARD:
                value = assumption.value
                scenario = replace(
                    scenario,
                    consumption_standard_id=None if value is None else str(value),
                )

    return replace(scenario, label=branch.label)


def plans_digest(plans: tuple[ProcessPlan, ...]) -> str:
    return digest(
        [
            {
                "agent": plan.agent_id,
                "recipe": plan.recipe_id,
                "batches": plan.intended_batches,
                "from": plan.from_period,
                "through": plan.through_period,
            }
            for plan in sorted(plans, key=lambda p: (p.agent_id, p.recipe_id))
        ]
    )
