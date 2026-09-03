"""Structured explanations.

D-001 says the software's job is to explain. That makes explanation a kernel
output, not a presentation concern: if the CLI derives its own account of why
a number came out the way it did, and a UI later derives another, the two can
drift — and "what the model says" diverging from "what the screen says" is a
corruption vector under this project's own threat model (D-010).

So propagation emits a Cause tree. Renderers walk it. Neither computes.

Every node carries its quantities as named components rather than a single
figure, and carries the coefficients and citations that produced them, so the
chain terminates in something a person can disagree with by name.
"""

from __future__ import annotations

import enum
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pint

from pdc.ontology import Citation


class CauseKind(enum.Enum):
    """What sort of fact a node states."""

    NEED_SHORTFALL = "need_shortfall"
    """A community did not receive what a standard says it requires."""

    INPUT_SHORTFALL = "input_shortfall"
    """A process could not obtain enough of an input."""

    PROCESS_UNDERRUN = "process_underrun"
    """A process ran below its intended scale."""

    BINDING_CONSTRAINT = "binding_constraint"
    """The limiting factor. Terminal: the chain stops here."""

    LAG = "lag"
    """An output was produced but is not available until a later period."""

    ALLOCATION = "allocation"
    """A quantity was made available by an explicit human decision."""


@dataclass(frozen=True, slots=True)
class Evidence:
    """A coefficient and its source that contributed to a number.

    This is the end of the line for an argument: someone who disputes a
    conclusion should be able to follow it down to a specific figure and the
    document it came from, and say "that one is wrong for our soil".
    """

    description: str
    quantity: pint.Quantity
    citation: Citation

    def to_json(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "magnitude": float(self.quantity.magnitude),
            "units": str(self.quantity.units),
            "citation": {
                "source": self.citation.source,
                "provenance": self.citation.provenance.value,
                "locator": self.citation.locator,
                "note": self.citation.note,
            },
        }


@dataclass(frozen=True, slots=True)
class Cause:
    """One link in a chain of consequence.

    Recursive: ``causes`` holds the reasons for this node, ending at a
    BINDING_CONSTRAINT or an ALLOCATION.
    """

    kind: CauseKind
    subject_id: str
    period: int
    summary: str
    detail: tuple[tuple[str, pint.Quantity], ...] = ()
    """Named quantities. Never one number: a shortfall is 'short 4,200 kgP of
    13,500 kgP required', not '31%'."""

    evidence: tuple[Evidence, ...] = ()
    causes: tuple[Cause, ...] = field(default_factory=tuple)

    def walk(self) -> Iterator[Cause]:
        """Depth-first over this node and everything beneath it."""
        yield self
        for cause in self.causes:
            yield from cause.walk()

    def binding_constraints(self) -> tuple[Cause, ...]:
        """The terminal constraints this chain bottoms out in."""
        return tuple(c for c in self.walk() if c.kind is CauseKind.BINDING_CONSTRAINT)

    def depth(self) -> int:
        return 1 + max((c.depth() for c in self.causes), default=0)

    def to_json(self) -> dict[str, Any]:
        """Canonical serialisation.

        The wire format a renderer consumes. Stable and boring on purpose:
        a UI reads this, it does not recompute from the world state.
        """
        return {
            "kind": self.kind.value,
            "subject": self.subject_id,
            "period": self.period,
            "summary": self.summary,
            "detail": [
                {"name": name, "magnitude": float(q.magnitude), "units": str(q.units)}
                for name, q in self.detail
            ],
            "evidence": [e.to_json() for e in self.evidence],
            "causes": [c.to_json() for c in self.causes],
        }


def render_text(cause: Cause, *, indent: int = 0, show_evidence: bool = True) -> str:
    """Render a cause tree as indented text.

    One renderer among several. It formats; it does not compute. A future web
    interface renders the same object as a diagram, and because both read the
    identical tree they cannot disagree about what happened.
    """
    pad = "  " * indent
    lines = [f"{pad}{'└─ ' if indent else ''}{cause.summary}"]

    for name, quantity in cause.detail:
        lines.append(f"{pad}     {name}: {quantity:~P}")

    if show_evidence:
        for item in cause.evidence:
            lines.append(f"{pad}     via {item.description} = {item.quantity:~P}")
            lines.append(f"{pad}         source: {item.citation}")

    for child in cause.causes:
        lines.append(render_text(child, indent=indent + 1, show_evidence=show_evidence))

    return "\n".join(lines)
