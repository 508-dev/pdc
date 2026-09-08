"""Coefficient inspection and diff.

The workflow this exists for, stated in D-010: "this farm is requesting ten
times the labour of any comparable farm — which variable are they tweaking?"
Signatures would say who asserted a figure. This says whether the figure is
plausible, which is the question people actually ask.
"""

from __future__ import annotations

import dataclasses

import pytest

from pdc.seed import build_reference_region
from pdc.seed.scenarios import grain_first_scenario, opening_state
from pdc.sim import (
    EXPORT_FORMAT,
    build_export,
    diff_recipes,
    is_diffable,
    recipes_payload,
    run_forward,
)
from pdc.units import Q


def _run(recipes=None):  # type: ignore[no-untyped-def]
    region = build_reference_region()
    return run_forward(
        grain_first_scenario(),
        agents=region.agents,
        recipes=recipes or region.recipes,
        standards=region.standards,
        compositions=region.compositions,
        opening=opening_state(),
    )


def _export(recipes=None):  # type: ignore[no-untyped-def]
    region = build_reference_region()
    used = recipes or region.recipes
    return build_export(
        _run(used), grain_first_scenario(), recipes=used, standards=region.standards
    )


def _with_alfalfa_phosphorus(kilograms: float):  # type: ignore[no-untyped-def]
    """A model that believes alfalfa draws less phosphorus."""
    region = build_reference_region()
    return tuple(
        dataclasses.replace(
            recipe,
            inputs=tuple(
                dataclasses.replace(flow, quantity=Q(kilograms, "kgP"))
                if flow.specification_id == "soil.phosphorus"
                else flow
                for flow in recipe.inputs
            ),
        )
        if recipe.id == "recipe.alfalfa"
        else recipe
        for recipe in region.recipes
    )


def test_exports_carry_the_coefficients_not_only_a_digest() -> None:
    """Format 1 could report *that* two models disagreed. Answering which
    number they disagree about needs the numbers to travel."""
    export = _export()
    assert export["format"] == EXPORT_FORMAT >= 2
    assert is_diffable(export)
    assert export["recipes"]


def test_identical_models_have_no_differences() -> None:
    region = build_reference_region()
    assert diff_recipes(_export(), region.recipes) == ()


def test_a_changed_coefficient_is_located_precisely() -> None:
    region = build_reference_region()
    differences = diff_recipes(_export(_with_alfalfa_phosphorus(15.0)), region.recipes)

    assert len(differences) == 1
    difference = differences[0]
    assert difference.recipe_id == "recipe.alfalfa"
    assert difference.specification_id == "soil.phosphorus"
    assert difference.theirs is not None and difference.mine is not None
    assert difference.theirs["magnitude"] == pytest.approx(15.0)
    assert difference.mine["magnitude"] == pytest.approx(22.5)
    assert difference.kind == "differs"


def test_a_ratio_is_given_only_between_comparable_figures() -> None:
    region = build_reference_region()
    difference = diff_recipes(_export(_with_alfalfa_phosphorus(45.0)), region.recipes)[0]
    assert difference.ratio == pytest.approx(2.0)


def test_no_ratio_across_incompatible_units() -> None:
    """A ratio across units would be exactly the reduction D-002 refuses.

    The export is assembled directly rather than by running the divergent
    model, because that model cannot run: a P2O5 recipe drawing on a P stock
    is refused by the units layer, which is the subject of the next test.
    """
    region = build_reference_region()
    theirs = tuple(
        dataclasses.replace(
            recipe,
            inputs=tuple(
                dataclasses.replace(flow, quantity=Q(1.0, "kgP2O5"))
                if flow.specification_id == "soil.phosphorus"
                else flow
                for flow in recipe.inputs
            ),
        )
        if recipe.id == "recipe.alfalfa"
        else recipe
        for recipe in region.recipes
    )
    export = _export()
    export["recipes"] = recipes_payload(theirs)

    difference = next(
        d for d in diff_recipes(export, region.recipes) if d.recipe_id == "recipe.alfalfa"
    )
    assert difference.ratio is None


def test_a_model_mixing_phosphorus_conventions_cannot_run_at_all() -> None:
    """The fertiliser-label trap, caught by the type system rather than by
    review: a recipe quoting P2O5 cannot silently draw on a stock of
    elemental P, even though both are "kilograms of phosphorus" in prose.
    """
    import pint

    region = build_reference_region()
    theirs = tuple(
        dataclasses.replace(
            recipe,
            inputs=tuple(
                dataclasses.replace(flow, quantity=Q(22.5, "kgP2O5"))
                if flow.specification_id == "soil.phosphorus"
                else flow
                for flow in recipe.inputs
            ),
        )
        if recipe.id == "recipe.alfalfa"
        else recipe
        for recipe in region.recipes
    )
    with pytest.raises(pint.DimensionalityError):
        _run(theirs)


def test_a_flow_present_on_one_side_only_is_reported() -> None:
    region = build_reference_region()
    theirs = tuple(
        dataclasses.replace(
            recipe,
            inputs=tuple(
                flow for flow in recipe.inputs if flow.specification_id != "water.irrigation"
            ),
        )
        if recipe.id == "recipe.alfalfa"
        else recipe
        for recipe in region.recipes
    )
    differences = diff_recipes(_export(theirs), region.recipes)
    assert any(d.kind == "only in mine" for d in differences)


def test_differences_carry_both_citations() -> None:
    """So the disagreement can be settled by looking at sources rather than
    by whoever argues longest."""
    region = build_reference_region()
    difference = diff_recipes(_export(_with_alfalfa_phosphorus(15.0)), region.recipes)[0]
    assert difference.their_citation
    assert difference.my_citation


def test_an_export_without_coefficients_is_not_diffable() -> None:
    export = _export()
    del export["recipes"]
    assert not is_diffable(export)


def test_the_payload_is_deterministically_ordered() -> None:
    region = build_reference_region()
    assert recipes_payload(region.recipes) == recipes_payload(tuple(reversed(region.recipes)))
