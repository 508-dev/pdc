"""The synthetic reference region."""

from __future__ import annotations

import pytest

from pdc.ontology import Action
from pdc.seed import build_reference_region
from pdc.seed import coefficients as coefficients_module


def test_region_builds() -> None:
    region = build_reference_region()
    assert len(region.agents) == 17
    assert len(region.recipes) == 6
    assert len(region.standards) == 2


def test_agent_tree_nests_recursively() -> None:
    """D-009: households nest in communes nest in valleys, and aggregation
    over a branch is one traversal with a depth argument."""
    region = build_reference_region()
    assert len(region.members_of("abbenay-valley")) == 6  # 4 communes + 2 ecosystems
    assert len(region.descendants_of("abbenay-valley")) == 16
    assert {a.id for a in region.members_of("northsetting")} == {
        "farm-a",
        "farm-d",
        "mill-north",
        "bakery-north",
    }


def test_ecosystems_are_agents_holding_stocks() -> None:
    """Valueflows sanctions this, so soil phosphorus drawdown needs no
    special case: the soil holds a stock and cropping decrements it."""
    region = build_reference_region()
    soil = region.agent("soil-valley")
    assert soil.kind == "ecosystem"
    stock = next(r for r in region.resources if r.custodian_id == "soil-valley")
    assert stock.specification_id == "soil.phosphorus"


def test_phosphorus_is_genuinely_scarce() -> None:
    """The fixture is only interesting if the constraint binds. With enough
    phosphorus for everything there is no allocation question."""
    region = build_reference_region()
    stock = next(r for r in region.resources if r.specification_id == "soil.phosphorus")
    arable = sum(
        a.attribute("land.arable_ha") for a in region.agents if a.has_attribute("land.arable_ha")
    )
    wheat = next(r for r in region.recipes if r.id == "recipe.wheat")
    per_ha = next(f for f in wheat.inputs if f.specification_id == "soil.phosphorus").quantity.to(
        "kgP"
    )
    assert (per_ha.magnitude * arable) > stock.quantity.to("kgP").magnitude


def test_alfalfa_output_is_lagged() -> None:
    """The lag is what makes this a multi-period problem: alfalfa cut this
    season feeds cattle in the next one, so a single-period model cannot see
    the consequence of starving it of phosphorus."""
    region = build_reference_region()
    alfalfa = next(r for r in region.recipes if r.id == "recipe.alfalfa")
    output = next(f for f in alfalfa.outputs if f.action is Action.PRODUCE)
    assert output.lag_periods == 1


def test_alfalfa_competes_with_wheat_for_phosphorus() -> None:
    """The tension the reference question turns on."""
    region = build_reference_region()

    def phosphorus_per_ha(recipe_id: str) -> float:
        recipe = next(r for r in region.recipes if r.id == recipe_id)
        flow = next(f for f in recipe.inputs if f.specification_id == "soil.phosphorus")
        return flow.quantity.to("kgP").magnitude

    assert phosphorus_per_ha("recipe.alfalfa") > phosphorus_per_ha("recipe.wheat")


def test_every_recipe_flow_carries_a_citation() -> None:
    """An uncited coefficient is a bug, not a TODO."""
    region = build_reference_region()
    for recipe in region.recipes:
        for flow in recipe.flows():
            assert flow.citation.source.strip(), f"{recipe.id} has an uncited flow"


def test_labour_flows_use_the_work_action() -> None:
    """Valueflows treats labour as an effort typed by skill, not a resource
    that moves around a warehouse."""
    region = build_reference_region()
    labour_ids = {s.id for s in region.resource_specifications if s.is_labour}
    for recipe in region.recipes:
        for flow in recipe.flows():
            if flow.specification_id in labour_ids:
                assert flow.action is Action.WORK


def test_fixture_coefficients_are_marked_illustrative() -> None:
    """The table is a demonstration, and says so in a way that is enforced."""
    illustrative = [c for c in coefficients_module.ALL if c.is_illustrative]
    assert illustrative, "coefficients claiming to be sourced should be checked"
    for coefficient in illustrative:
        with pytest.raises(ValueError, match="illustrative"):
            coefficient.check_usable()


def test_both_standards_evaluate_for_every_community() -> None:
    region = build_reference_region()
    communes = [a for a in region.agents if a.kind == "commune"]
    assert len(communes) == 4
    for agent in communes:
        for standard in region.standards:
            assert standard.evaluate(agent).to("kcal/day").magnitude > 0
