"""NeedStandard and ResponseModel invariants from D-006 and D-008."""

from __future__ import annotations

import pytest

from pdc.needs import Attr, BinOp, ExpressionError, Lit, NeedStandard, ResponseModel
from pdc.ontology import Agent, Citation, Provenance

CITATION = Citation("a test", Provenance.ILLUSTRATIVE)
EXPRESSION = BinOp("mul", Attr("population"), Lit(2100.0, "kcal/day"))


def _standard(**overrides: object) -> NeedStandard:
    kwargs: dict[str, object] = {
        "id": "test:energy",
        "name": "Test",
        "author_id": "someone",
        "citation": CITATION,
        "version": "1",
        "expression": EXPRESSION,
        "produces_specification_id": "food.energy",
        "requires": ("population",),
    }
    kwargs.update(overrides)
    return NeedStandard(**kwargs)  # type: ignore[arg-type]


def test_a_citation_cannot_be_constructed_without_a_source() -> None:
    """First line of defence: Citation itself rejects a blank source."""
    with pytest.raises(ValueError, match="must name a source"):
        Citation("", Provenance.PUBLISHED)


def test_a_standard_without_a_citation_is_rejected() -> None:
    """D-006 backstop. Citation already refuses a blank source, so this can
    only be reached by mutating one past its constructor — which is exactly
    the case a backstop is for."""
    blanked = Citation("placeholder", Provenance.ILLUSTRATIVE)
    object.__setattr__(blanked, "source", "   ")
    with pytest.raises(ValueError, match="no citation"):
        _standard(citation=blanked)


def test_declared_dependencies_are_validated_before_evaluation() -> None:
    """Fails on the declared requirement, not on the attribute lookup, so the
    error names the standard rather than an opaque KeyError mid-expression."""
    standard = _standard()
    agent = Agent("t", "Test", "commune")
    with pytest.raises(ExpressionError, match="requires attributes"):
        standard.evaluate(agent)


def test_all_missing_attributes_are_reported_at_once() -> None:
    standard = _standard(requires=("population", "climate.mean_temp_c"))
    agent = Agent("t", "Test", "commune")
    with pytest.raises(ExpressionError) as excinfo:
        standard.evaluate(agent)
    assert "climate.mean_temp_c" in str(excinfo.value)
    assert "population" in str(excinfo.value)


def test_evaluation_produces_a_quantity() -> None:
    agent = Agent("t", "Test", "commune", attributes=(("population", 12000.0),))
    assert _standard().evaluate(agent).to("kcal/day").magnitude == pytest.approx(25_200_000.0)


def test_standards_are_peers_with_no_built_in_ordering() -> None:
    """D-006: no ladder of tiers. Two standards are just two claims."""
    assert not hasattr(NeedStandard, "tier")
    assert not hasattr(NeedStandard, "rank")
    assert not hasattr(NeedStandard, "priority")


def test_response_model_cannot_be_enabled_by_default() -> None:
    """D-008: unmet need reports a shortfall and stops unless a human opts in.

    A ResponseModel asserts what happens to people when they go hungry. That
    claim must never arrive by default.
    """
    with pytest.raises(ValueError, match="may not be enabled by default"):
        ResponseModel(
            id="r",
            name="Reduced labour capacity",
            author_id="someone",
            citation=CITATION,
            version="1",
            responds_to_standard_id="test:energy",
            expression=Lit(1.0, "dimensionless"),
            affects="labour_capacity",
            enabled_by_default=True,
        )


def test_response_model_is_a_distinct_type_from_need_standard() -> None:
    assert not issubclass(ResponseModel, NeedStandard)
    assert not issubclass(NeedStandard, ResponseModel)
