"""Provenance for numbers that describe the physical world.

Every coefficient — a yield, a nutrient content, a labour requirement, a
conversion factor, a process lag — carries where it came from. This is not
bookkeeping hygiene; it is the mechanism by which one community can look at
another's model and ask why their numbers differ (D-010).

An uncited coefficient is a bug. Where a plausible-but-unsourced figure is
genuinely needed for a fixture, it is marked ``ILLUSTRATIVE`` so that it can
never quietly migrate into a real model.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

import pint


class Provenance(enum.Enum):
    """Where a coefficient came from, and therefore how much to trust it."""

    MEASURED = "measured"
    """Observed locally, by the agent asserting it."""

    PUBLISHED = "published"
    """Taken from a citable external source."""

    DELIBERATED = "deliberated"
    """Agreed by a recorded human process rather than measured."""

    ESTIMATED = "estimated"
    """Someone's judgement. Cited to the person, at least."""

    ILLUSTRATIVE = "illustrative"
    """Plausible but unsourced. Fixtures and demos only.

    Never valid in a model anyone relies on. ``Coefficient.check_usable()``
    rejects these outside test fixtures.
    """


@dataclass(frozen=True, slots=True)
class Citation:
    """Where a number came from."""

    source: str
    """Human-readable source: document title, dataset name, or person."""

    provenance: Provenance
    locator: str | None = None
    """DOI, URL, table number, page, or dataset identifier."""

    note: str | None = None
    """Anything a reader needs in order to interpret the figure correctly:
    the region it applies to, the management assumptions, the year."""

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("a citation must name a source")

    def __str__(self) -> str:
        parts = [self.source]
        if self.locator:
            parts.append(self.locator)
        return f"{' — '.join(parts)} [{self.provenance.value}]"


@dataclass(frozen=True, slots=True)
class Coefficient:
    """A dimensioned number with its provenance attached.

    Deliberately not a bare ``Quantity``. The whole auditability argument
    depends on it being impossible to introduce a physical constant without
    saying where it came from.
    """

    name: str
    value: pint.Quantity
    citation: Citation
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_illustrative(self) -> bool:
        return self.citation.provenance is Provenance.ILLUSTRATIVE

    def check_usable(self) -> None:
        """Raise if this coefficient must not be used in a real model."""
        if self.is_illustrative:
            raise ValueError(
                f"coefficient {self.name!r} is illustrative "
                f"({self.citation}) and must not be used outside fixtures"
            )

    def __str__(self) -> str:
        marker = " (ILLUSTRATIVE)" if self.is_illustrative else ""
        return f"{self.name} = {self.value:~P}{marker}"
