"""Coefficients carry provenance, and illustrative ones refuse to be used."""

from __future__ import annotations

import pytest

from pdc.ontology import Citation, Coefficient, Provenance
from pdc.units import Q


def test_a_citation_must_name_a_source() -> None:
    with pytest.raises(ValueError, match="must name a source"):
        Citation(source="   ", provenance=Provenance.PUBLISHED)


def test_illustrative_coefficients_refuse_to_be_used() -> None:
    """The guard that stops a fixture number reaching a real model."""
    coefficient = Coefficient(
        name="wheat.yield",
        value=Q(3.0, "tFW/ha_season"),
        citation=Citation("made up for a demo", Provenance.ILLUSTRATIVE),
    )
    assert coefficient.is_illustrative
    with pytest.raises(ValueError, match="illustrative"):
        coefficient.check_usable()


def test_sourced_coefficients_are_usable() -> None:
    coefficient = Coefficient(
        name="human.energy.survival",
        value=Q(2100.0, "kcal/day"),
        citation=Citation("Sphere Handbook 2018", Provenance.PUBLISHED, "spherestandards.org"),
    )
    coefficient.check_usable()
    assert not coefficient.is_illustrative
