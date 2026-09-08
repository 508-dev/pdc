"""The URL is the scenario.

Every control in the explorer maps to an `Assumption`, so anything the
interface can express is also a branch, a URL, and an export. That is the
property that keeps the audit right applying to what people actually did in
the interface, rather than only to scenarios someone wrote in Python.

Out-of-range values are rejected rather than clamped. Silently adjusting what
was asked for would make a URL mean something other than it says, which for a
tool about being checkable is the wrong trade.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

from pdc.seed.scenarios import (
    CONSUMPTION_STANDARD,
    allocation_for,
    phosphorus_shares,
    reference_plans,
)
from pdc.sim import Assumption, AssumptionKind, Branch, Scenario

MAX_PERIODS = 12
NO_CONSUMPTION = "none"


class ParameterError(ValueError):
    """A parameter that cannot be honoured as written."""


@dataclass(frozen=True, slots=True)
class ExploreParams:
    """What the reader has asked to see."""

    alfalfa_share: float = 0.0
    periods: int = 3
    standard_id: str | None = CONSUMPTION_STANDARD
    """None means nothing is consumed and stocks accumulate."""

    @classmethod
    def parse(cls, values: dict[str, str], known_standards: set[str]) -> ExploreParams:
        raw_share = values.get("alfalfa", "0")
        try:
            share = float(raw_share) / 100.0
        except ValueError as exc:
            raise ParameterError(f"alfalfa share must be a number, got {raw_share!r}") from exc
        if not 0.0 <= share <= 1.0:
            raise ParameterError(f"alfalfa share must be between 0 and 100, got {raw_share!r}")

        raw_periods = values.get("periods", "3")
        try:
            periods = int(raw_periods)
        except ValueError as exc:
            raise ParameterError(f"periods must be a whole number, got {raw_periods!r}") from exc
        if not 1 <= periods <= MAX_PERIODS:
            raise ParameterError(f"periods must be between 1 and {MAX_PERIODS}")

        standard = values.get("standard", CONSUMPTION_STANDARD)
        if standard == NO_CONSUMPTION:
            standard_id = None
        elif standard in known_standards:
            standard_id = standard
        else:
            raise ParameterError(f"no standard {standard!r}")

        return cls(alfalfa_share=share, periods=periods, standard_id=standard_id)

    @property
    def alfalfa_percent(self) -> float:
        return self.alfalfa_share * 100.0

    def to_query(self) -> str:
        return urlencode(
            {
                "alfalfa": f"{self.alfalfa_percent:g}",
                "periods": self.periods,
                "standard": self.standard_id or NO_CONSUMPTION,
            }
        )

    def to_branch(self) -> Branch:
        """The assumptions behind this view, named and reasoned.

        One slider becomes several assumptions, one per farm, because that is
        what it actually does. Recording the dial position instead would hide
        the fact that dividing within each group by area is itself a choice.
        """
        share_text = f"{self.alfalfa_percent:g}% of the phosphorus stock to forage"
        assumptions = [
            Assumption(
                kind=AssumptionKind.SET_ALLOCATION_SHARE,
                target=(agent_id, specification_id),
                value=quantity,  # type: ignore[arg-type]
                rationale=share_text,
            )
            for (agent_id, specification_id), quantity in sorted(
                phosphorus_shares(self.alfalfa_share).items()
            )
        ]

        assumptions.append(
            Assumption(
                kind=AssumptionKind.SET_PERIODS,
                target=("scenario",),
                value=self.periods,
                rationale="how many seasons to run forward",
            )
        )
        assumptions.append(
            Assumption(
                kind=AssumptionKind.SET_CONSUMPTION_STANDARD,
                target=("scenario",),
                value=self.standard_id,
                rationale=(
                    "the standard governing how much people eat"
                    if self.standard_id
                    else "nothing is consumed; stocks accumulate"
                ),
            )
        )

        return Branch(label=f"alfalfa-{self.alfalfa_percent:g}", assumptions=tuple(assumptions))

    def to_scenario(self) -> Scenario:
        """The scenario this view shows.

        Built by applying the branch to a base, so the branch is the single
        description of the view and cannot fall out of step with it.
        """
        from pdc.sim import apply_branch

        base = Scenario(
            label="baseline",
            allocation=allocation_for(0.0, label="baseline"),
            plans=reference_plans(),
            periods=self.periods,
            consumption_standard_id=self.standard_id,
        )
        return apply_branch(base, self.to_branch())
