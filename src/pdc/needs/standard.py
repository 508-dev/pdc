"""NeedStandard and ResponseModel.

Valueflows has no concept of need. It has Intent, which is something an agent
*declares*. PDC derives requirement from population and a cited standard
whether or not anyone asked (D-006).

There is no built-in ladder of tiers and no privileged standard. 'Survival',
'adequate', and 'comfortable' are simply standards someone published, in an
order someone chose. Communities declare which they wish to be evaluated
against; the system reports state against each.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pint

from pdc.needs.expr import AttributeSource, ExpressionError, Node, evaluate_quantity
from pdc.ontology.citation import Citation


@dataclass(frozen=True, slots=True)
class NeedStandard:
    """A cited, versioned claim about what an agent requires.

    Immutable once published. Revising a standard means publishing a new
    version, so that a scenario computed last year can still be reproduced.
    """

    id: str
    name: str
    author_id: str
    citation: Citation
    version: str
    expression: Node
    produces_specification_id: str
    requires: tuple[str, ...] = field(default_factory=tuple)
    """Agent attributes this standard reads. Declared up front so that a
    missing attribute is a validation failure before evaluation rather than a
    silent zero during it."""

    applies_to: str | None = None
    """Free-text scope note: who this standard is for. Not a predicate yet;
    matching is the caller's job until there is a real use for automation."""

    def __post_init__(self) -> None:
        if not self.citation.source.strip():
            raise ValueError(
                f"need standard {self.id!r} has no citation; "
                "a standard with no source is not usable (D-006)"
            )

    def validate_against(self, agent: AttributeSource) -> None:
        """Check declared dependencies before evaluating.

        Fails loudly and completely: reports every missing attribute at once
        rather than one per attempt.
        """
        missing = [path for path in self.requires if not agent.has_attribute(path)]
        if missing:
            raise ExpressionError(
                f"standard {self.id!r} requires attributes that this agent lacks: "
                f"{', '.join(sorted(missing))}"
            )

    def evaluate(
        self,
        agent: AttributeSource,
        standards: dict[str, NeedStandard] | None = None,
    ) -> pint.Quantity:
        """Compute the requirement this standard implies for an agent."""
        self.validate_against(agent)
        try:
            return evaluate_quantity(self.expression, agent, standards=standards)
        except ExpressionError as exc:
            raise ExpressionError(f"standard {self.id!r}: {exc}") from exc


@dataclass(frozen=True, slots=True)
class ResponseModel:
    """What happens when a need is not met.

    Deliberately a *different type* from NeedStandard (D-008). A NeedStandard
    states a requirement. A ResponseModel asserts what happens to human beings
    when they do not get it — reduced labour output, morbidity, mortality —
    and that is a categorically different and far more contestable claim.

    **Off by default.** The default behaviour on unmet need is to report the
    shortfall in physical units and stop. Simulation and game contexts opt in
    by name; a live deployment should have to choose it deliberately and know
    that it has.

    Mortality and other absorbing states belong to the population model, not
    here, which keeps NeedStandard a pure function of current attributes.
    """

    id: str
    name: str
    author_id: str
    citation: Citation
    version: str
    responds_to_standard_id: str
    expression: Node
    affects: str
    """What the result modifies: 'labour_capacity', 'morbidity', and so on."""

    enabled_by_default: bool = False

    def __post_init__(self) -> None:
        if self.enabled_by_default:
            raise ValueError(
                f"response model {self.id!r} may not be enabled by default; "
                "unmet need reports a shortfall and stops unless a human opts in (D-008)"
            )
