"""Dimensional costing: the no-reduction guarantee, enforced.

D-002 is the project's load-bearing commitment. These tests exist to make it
expensive to break by accident.
"""

from __future__ import annotations

import pint
import pytest

from pdc.costing import (
    AttributionError,
    AttributionRecord,
    CircularProductionError,
    CostVector,
    ExplicitShares,
    JointCostError,
    NoAttributionRuleError,
    ProportionalToOutput,
    ScalarReductionError,
    SingleOutput,
    Unattributed,
    rollup,
)
from pdc.ontology import Action, Citation, Provenance, RecipeFlow, RecipeProcess
from pdc.seed import build_reference_region
from pdc.units import Q

CITATION = Citation("a test", Provenance.ILLUSTRATIVE)


# --------------------------------------------------------------------------
# The reductions that must not exist
# --------------------------------------------------------------------------


def _mixed() -> CostVector:
    return CostVector.of({"soil.phosphorus": Q(3.0, "kgP"), "labour.field": Q(7.0, "labour_hour")})


def test_cost_vector_refuses_to_become_a_float() -> None:
    with pytest.raises(ScalarReductionError, match="cannot be reduced"):
        float(_mixed())


def test_cost_vector_refuses_to_become_an_int() -> None:
    with pytest.raises(ScalarReductionError):
        int(_mixed())


def test_cost_vector_has_no_total() -> None:
    """There is no .total(), deliberately, and adding one is not a
    contribution (AGENTS.md)."""
    assert not hasattr(CostVector, "total")
    assert not hasattr(CostVector, "sum")
    assert not hasattr(CostVector, "value")


def test_cost_vectors_are_not_ordered() -> None:
    """Most pairs are genuinely incomparable: cheaper in phosphorus, dearer in
    labour. Ranking them requires an exchange rate this project refuses."""
    cheap = CostVector.of({"soil.phosphorus": Q(1.0, "kgP")})
    dear = CostVector.of({"soil.phosphorus": Q(9.0, "kgP")})
    for operation in (lambda: cheap < dear, lambda: cheap > dear, lambda: cheap <= dear):
        with pytest.raises(ScalarReductionError, match="not ordered"):
            operation()


def test_builtin_sum_cannot_silently_collapse_a_vector() -> None:
    with pytest.raises(TypeError):
        sum([_mixed(), _mixed()])  # type: ignore[list-item]


# --------------------------------------------------------------------------
# Aggregation within a dimension is legal
# --------------------------------------------------------------------------


def test_adding_sums_matching_components() -> None:
    """Aggregate freely WITHIN a dimension (D-002)."""
    combined = CostVector.of({"soil.phosphorus": Q(2.0, "kgP")}) + CostVector.of(
        {"soil.phosphorus": Q(3.0, "kgP")}
    )
    assert combined.require("soil.phosphorus").magnitude == pytest.approx(5.0)


def test_adding_keeps_distinct_components_distinct() -> None:
    combined = CostVector.of({"soil.phosphorus": Q(2.0, "kgP")}) + CostVector.of(
        {"labour.field": Q(4.0, "labour_hour")}
    )
    assert set(combined.specifications()) == {"soil.phosphorus", "labour.field"}


def test_same_component_with_incompatible_units_raises() -> None:
    """A specification has one unit. Two claims about it in different
    conventions is the P/P2O5 trap wearing a different hat."""
    with pytest.raises(pint.DimensionalityError):
        _ = CostVector.of({"soil.phosphorus": Q(1.0, "kgP")}) + CostVector.of(
            {"soil.phosphorus": Q(1.0, "kgP2O5")}
        )


def test_components_are_deterministically_ordered() -> None:
    vector = CostVector.of(
        {"water.irrigation": Q(1.0, "m^3"), "labour.field": Q(1.0, "labour_hour")}
    )
    assert list(vector.specifications()) == sorted(vector.specifications())


def test_absent_component_is_none_not_zero() -> None:
    """Absent and zero are different facts, and inventing a unit for the
    absent case is how silent errors start."""
    assert CostVector().component("soil.phosphorus") is None


def test_scaling_multiplies_every_component() -> None:
    scaled = _mixed().scaled(2.0)
    assert scaled.require("soil.phosphorus").magnitude == pytest.approx(6.0)
    assert scaled.require("labour.field").magnitude == pytest.approx(14.0)


# --------------------------------------------------------------------------
# Joint production
# --------------------------------------------------------------------------


def _dairy_with_manure() -> RecipeProcess:
    """A joint-producing recipe: milk and manure from the same cow-year."""
    return RecipeProcess(
        id="recipe.dairy.joint",
        name="Dairying with manure",
        process_specification_id="milk.cattle",
        inputs=(
            RecipeFlow(Action.CONSUME, "alfalfa", Q(2.2, "tDM"), CITATION),
            RecipeFlow(Action.WORK, "labour.dairy", Q(40.0, "labour_hour"), CITATION),
        ),
        outputs=(
            RecipeFlow(Action.PRODUCE, "milk", Q(5.5, "tFW"), CITATION),
            RecipeFlow(Action.PRODUCE, "manure", Q(11.0, "tFW"), CITATION),
        ),
    )


def test_joint_production_without_a_rule_refuses() -> None:
    """Every division of a joint cost is a value judgement, so PDC will not
    pick one silently (docs/ontology.md 2.2)."""
    with pytest.raises(NoAttributionRuleError, match="value judgement"):
        rollup("milk", Q(1.0, "tFW"), [_dairy_with_manure()])


def test_single_output_rule_charges_everything_to_one_output() -> None:
    result = rollup("milk", Q(5.5, "tFW"), [_dairy_with_manure()], attribution=SingleOutput("milk"))
    assert result.cost.require("alfalfa").to("tDM").magnitude == pytest.approx(2.2)


def test_single_output_rule_names_the_rule_in_the_result() -> None:
    """A cost vector always answers 'under what assumption?' alongside
    'how much?'."""
    result = rollup("milk", Q(5.5, "tFW"), [_dairy_with_manure()], attribution=SingleOutput("milk"))
    assert AttributionRecord("recipe.dairy.joint", "single-output:milk") in result.cost.attributions


def test_explicit_shares_divide_the_cost() -> None:
    rule = ExplicitShares((("milk", 0.75), ("manure", 0.25)), label="chakar-2027")
    result = rollup("milk", Q(5.5, "tFW"), [_dairy_with_manure()], attribution=rule)
    assert result.cost.require("alfalfa").to("tDM").magnitude == pytest.approx(2.2 * 0.75)


def test_explicit_shares_must_sum_to_one() -> None:
    rule = ExplicitShares((("milk", 0.75), ("manure", 0.75)))
    with pytest.raises(AttributionError, match="sum to"):
        rollup("milk", Q(1.0, "tFW"), [_dairy_with_manure()], attribution=rule)


def test_explicit_shares_must_cover_every_output() -> None:
    """An unstated share is not the same as a zero one."""
    rule = ExplicitShares((("milk", 1.0),))
    with pytest.raises(AttributionError, match="no share for outputs"):
        rollup("milk", Q(1.0, "tFW"), [_dairy_with_manure()], attribution=rule)


def test_single_output_rule_must_name_a_real_output() -> None:
    with pytest.raises(AttributionError, match="does not produce"):
        rollup("milk", Q(1.0, "tFW"), [_dairy_with_manure()], attribution=SingleOutput("butter"))


def test_proportional_rule_divides_by_output_quantity() -> None:
    result = rollup(
        "milk", Q(5.5, "tFW"), [_dairy_with_manure()], attribution=ProportionalToOutput()
    )
    # milk 5.5 t, manure 11.0 t, so milk bears one third.
    assert result.cost.require("alfalfa").to("tDM").magnitude == pytest.approx(2.2 / 3.0)


def test_proportional_rule_refuses_incommensurable_outputs() -> None:
    """Dividing 'in proportion' between tonnes and hectares is a category
    error with a number attached."""
    recipe = RecipeProcess(
        id="recipe.odd",
        name="Incommensurable outputs",
        process_specification_id="p",
        inputs=(RecipeFlow(Action.CONSUME, "alfalfa", Q(1.0, "tDM"), CITATION),),
        outputs=(
            RecipeFlow(Action.PRODUCE, "milk", Q(1.0, "tFW"), CITATION),
            RecipeFlow(Action.PRODUCE, "grazing", Q(1.0, "ha_season"), CITATION),
        ),
    )
    with pytest.raises(AttributionError, match="not commensurable"):
        rollup("milk", Q(1.0, "tFW"), [recipe], attribution=ProportionalToOutput())


def test_unattributed_costs_refuse_to_be_added() -> None:
    """The awkwardness is the information: those costs really are one set of
    inputs, and treating them as two is wrong."""
    recipes = [_dairy_with_manure()]
    milk = rollup("milk", Q(5.5, "tFW"), recipes, attribution=Unattributed()).cost
    manure = rollup("manure", Q(11.0, "tFW"), recipes, attribution=Unattributed()).cost

    assert milk.joint_groups == manure.joint_groups != frozenset()
    with pytest.raises(JointCostError, match="double counts"):
        _ = milk + manure


def test_unattributed_charges_the_whole_cost_to_each_output() -> None:
    recipes = [_dairy_with_manure()]
    milk = rollup("milk", Q(5.5, "tFW"), recipes, attribution=Unattributed()).cost
    assert milk.require("alfalfa").to("tDM").magnitude == pytest.approx(2.2)


# --------------------------------------------------------------------------
# Rollup through the reference region
# --------------------------------------------------------------------------


def test_bread_carries_phosphorus_from_the_field() -> None:
    """The chain that matters: bakery -> mill -> wheat field -> soil.

    1 t bread needs 1/1.5 t flour, which needs (1/1.5)/0.78 t grain, which
    needs that over 3 t/ha of land, at 10.5 kgP/ha.
    """
    region = build_reference_region()
    result = rollup("bread", Q(1.0, "tFW"), region.recipes)
    expected = (1.0 / 1.5) / 0.78 / 3.0 * 10.5
    assert result.cost.require("soil.phosphorus").to("kgP").magnitude == pytest.approx(expected)


def test_bread_carries_labour_from_every_stage() -> None:
    region = build_reference_region()
    cost = rollup("bread", Q(1.0, "tFW"), region.recipes).cost
    assert set(cost.specifications()) >= {
        "labour.bake",
        "labour.field",
        "labour.mill",
        "land.arable",
        "soil.phosphorus",
        "water.irrigation",
    }


def test_rollup_result_is_never_a_single_number() -> None:
    region = build_reference_region()
    cost = rollup("bread", Q(1.0, "tFW"), region.recipes).cost
    assert len(cost) > 1
    with pytest.raises(ScalarReductionError):
        float(cost)


def test_primary_inputs_terminate_the_walk() -> None:
    region = build_reference_region()
    result = rollup("soil.phosphorus", Q(5.0, "kgP"), region.recipes)
    assert result.cost.specifications() == ("soil.phosphorus",)


def test_alfalfa_carries_more_phosphorus_than_wheat_per_hectare() -> None:
    """The tension the reference question turns on, now costed."""
    region = build_reference_region()
    wheat = rollup("wheat.grain", Q(3.0, "tFW"), region.recipes).cost
    alfalfa = rollup("alfalfa", Q(9.0, "tDM"), region.recipes).cost
    assert alfalfa.require("soil.phosphorus") > wheat.require("soil.phosphorus")


def test_production_cycles_are_reported_not_looped() -> None:
    """Real in agriculture; resolved by a fixed-point solve in M4, not here."""
    compost = RecipeProcess(
        "recipe.compost",
        "Compost",
        "p",
        inputs=(RecipeFlow(Action.CONSUME, "alfalfa", Q(1.0, "tDM"), CITATION),),
        outputs=(RecipeFlow(Action.PRODUCE, "soil.phosphorus", Q(1.0, "kgP"), CITATION),),
    )
    grow = RecipeProcess(
        "recipe.grow",
        "Grow",
        "p",
        inputs=(RecipeFlow(Action.CONSUME, "soil.phosphorus", Q(1.0, "kgP"), CITATION),),
        outputs=(RecipeFlow(Action.PRODUCE, "alfalfa", Q(1.0, "tDM"), CITATION),),
    )
    with pytest.raises(CircularProductionError, match="production cycle"):
        rollup("alfalfa", Q(1.0, "tDM"), [compost, grow])


def test_competing_production_routes_are_not_chosen_between() -> None:
    """Choosing a route is a decision for people, not for a rollup (D-001)."""

    def route(recipe_id: str, labour: float) -> RecipeProcess:
        return RecipeProcess(
            recipe_id,
            recipe_id,
            "p",
            inputs=(RecipeFlow(Action.WORK, "labour.field", Q(labour, "labour_hour"), CITATION),),
            outputs=(RecipeFlow(Action.PRODUCE, "bread", Q(1.0, "tFW"), CITATION),),
        )

    with pytest.raises(NoAttributionRuleError, match="recipes produce"):
        rollup("bread", Q(1.0, "tFW"), [route("a", 1.0), route("b", 2.0)])


def test_cite_flows_do_not_incur_cost() -> None:
    """Charging for knowledge is how enclosure starts."""
    recipe = RecipeProcess(
        "recipe.cited",
        "Uses a design",
        "p",
        inputs=(
            RecipeFlow(Action.CITE, "design.plough", Q(1.0, "dimensionless"), CITATION),
            RecipeFlow(Action.WORK, "labour.field", Q(2.0, "labour_hour"), CITATION),
        ),
        outputs=(RecipeFlow(Action.PRODUCE, "bread", Q(1.0, "tFW"), CITATION),),
    )
    cost = rollup("bread", Q(1.0, "tFW"), [recipe]).cost
    assert cost.specifications() == ("labour.field",)


def test_require_raises_for_an_absent_component() -> None:
    """The assertive counterpart to component(): fail loudly rather than
    propagating a None into arithmetic."""
    with pytest.raises(KeyError, match="no component"):
        CostVector.of({"labour.field": Q(1.0, "labour_hour")}).require("soil.phosphorus")
