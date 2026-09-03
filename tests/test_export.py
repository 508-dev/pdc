"""Branches, content addressing, and independent verification.

D-010 says the audit right is real because anyone can recompute. These tests
are what make that claim true rather than aspirational.
"""

from __future__ import annotations

import dataclasses

import pytest

from pdc.seed import build_reference_region
from pdc.seed.scenarios import grain_first_scenario, opening_state, split_scenario
from pdc.sim import (
    Assumption,
    AssumptionKind,
    Branch,
    apply_branch,
    build_export,
    canonical_json,
    digest,
    run_forward,
    verify,
)
from pdc.units import Q


def _run(scenario):  # type: ignore[no-untyped-def]
    region = build_reference_region()
    return run_forward(
        scenario,
        agents=region.agents,
        recipes=region.recipes,
        standards=region.standards,
        compositions=region.compositions,
        opening=opening_state(),
    )


# --------------------------------------------------------------------------
# Canonical form
# --------------------------------------------------------------------------


def test_canonical_json_sorts_keys() -> None:
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_digest_is_stable_across_key_order() -> None:
    """Two people who built the same value different ways must agree."""
    assert digest({"a": 1, "b": 2}) == digest({"b": 2, "a": 1})


def test_digest_changes_when_a_value_changes() -> None:
    assert digest({"yield": 3.0}) != digest({"yield": 3.1})


# --------------------------------------------------------------------------
# Branches
# --------------------------------------------------------------------------


def _share(agent: str, kilograms: float, why: str = "") -> Assumption:
    return Assumption(
        kind=AssumptionKind.SET_ALLOCATION_SHARE,
        target=(agent, "soil.phosphorus"),
        value=Q(kilograms, "kgP"),
        rationale=why,
    )


def test_branch_digest_ignores_the_label() -> None:
    """Two branches making the same changes to the same parent are the same
    branch, whatever anyone called them."""
    first = Branch("chakar-proposal", (_share("farm-b", 4400.0),))
    second = Branch("northsetting-counter", (_share("farm-b", 4400.0),))
    assert first.digest == second.digest


def test_branch_digest_changes_with_assumptions() -> None:
    assert (
        Branch("a", (_share("farm-b", 4400.0),)).digest
        != Branch("a", (_share("farm-b", 4500.0),)).digest
    )


def test_forking_records_the_parent() -> None:
    root = Branch("baseline")
    child = root.fork("more-alfalfa", _share("farm-b", 4400.0))
    assert child.parent == root.digest
    assert child.digest != root.digest


def test_diff_reports_which_premises_differ() -> None:
    """The workflow: two communities disagree about an outcome, so they
    compare the premises rather than the conclusions."""
    mine = Branch("mine", (_share("farm-b", 4400.0, "keep the herds fed"),))
    yours = Branch("yours", (_share("farm-b", 0.0, "grain first"),))
    lines = mine.diff(yours)
    assert any("only in mine" in line for line in lines)
    assert any("only in yours" in line for line in lines)
    assert any("keep the herds fed" in line for line in lines)


def test_branch_round_trips_through_json() -> None:
    branch = Branch("proposal", (_share("farm-b", 4400.0, "because"),), parent="abc")
    assert Branch.from_json(branch.to_json()) == branch


def test_applying_a_branch_leaves_the_base_untouched() -> None:
    """Purity is what makes branching cheap and exploration safe."""
    base = grain_first_scenario()
    before = dataclasses.replace(base)
    apply_branch(base, Branch("fork", (_share("farm-b", 4400.0),)))
    assert base == before


def test_allocation_assumption_changes_the_outcome() -> None:
    base = grain_first_scenario()
    branch = Branch(
        "feed-the-herds",
        (_share("farm-b", 4400.0, "Chakar has no grain farm and starves without alfalfa"),),
    )
    derived = apply_branch(base, branch)

    granted = derived.allocation.granted("farm-b", "soil.phosphorus")
    assert granted is not None
    assert granted.to("kgP").magnitude == 4400.0
    assert _run(base).needs_for("chakar", "abbenay-valley:food-energy-adequate")[
        1
    ].available.magnitude == pytest.approx(0.0)
    assert (
        _run(derived)
        .needs_for("chakar", "abbenay-valley:food-energy-adequate")[1]
        .available.magnitude
        > 0.0
    )


def test_plan_scale_and_removal_assumptions_apply() -> None:
    base = grain_first_scenario()
    scaled = apply_branch(
        base,
        Branch(
            "half-the-wheat",
            (Assumption(AssumptionKind.SET_PLAN_SCALE, ("farm-a", "recipe.wheat"), 450.0),),
        ),
    )
    assert any(p.agent_id == "farm-a" and p.intended_batches == 450.0 for p in scaled.plans)

    removed = apply_branch(
        base,
        Branch(
            "no-dairy",
            (Assumption(AssumptionKind.REMOVE_PLAN, ("ranch-c", "recipe.dairy")),),
        ),
    )
    assert not any(p.agent_id == "ranch-c" and p.recipe_id == "recipe.dairy" for p in removed.plans)


def test_periods_and_consumption_assumptions_apply() -> None:
    base = grain_first_scenario()
    derived = apply_branch(
        base,
        Branch(
            "longer-and-hungrier",
            (
                Assumption(AssumptionKind.SET_PERIODS, ("scenario",), 5),
                Assumption(
                    AssumptionKind.SET_CONSUMPTION_STANDARD,
                    ("scenario",),
                    "sphere-2018:food-energy",
                ),
            ),
        ),
    )
    assert derived.periods == 5
    assert derived.consumption_standard_id == "sphere-2018:food-energy"


# --------------------------------------------------------------------------
# Export and verification
# --------------------------------------------------------------------------


def _export(scenario):  # type: ignore[no-untyped-def]
    region = build_reference_region()
    return build_export(
        _run(scenario), scenario, recipes=region.recipes, standards=region.standards
    )


def test_an_export_reproduces_exactly_against_the_same_model() -> None:
    scenario = grain_first_scenario()
    region = build_reference_region()
    result = verify(
        _export(scenario), _run(scenario), recipes=region.recipes, standards=region.standards
    )
    assert result.reproduced
    assert result.recipes_match and result.standards_match
    assert "reproduced exactly" in result.summary()


def test_a_different_scenario_does_not_reproduce() -> None:
    region = build_reference_region()
    result = verify(
        _export(grain_first_scenario()),
        _run(split_scenario()),
        recipes=region.recipes,
        standards=region.standards,
    )
    assert not result.reproduced


def test_disagreeing_about_coefficients_is_reported_as_disagreement() -> None:
    """Not a bug — the disagreement the project exists to surface.

    Someone whose soil gives up phosphorus differently gets different answers,
    and the verifier should say so in those terms rather than implying one
    side is broken.
    """
    region = build_reference_region()

    # Someone whose alfalfa takes less phosphorus from their soil.
    theirs = dataclasses.replace(
        region,
        recipes=tuple(
            dataclasses.replace(
                recipe,
                inputs=tuple(
                    dataclasses.replace(flow, quantity=Q(15.0, "kgP"))
                    if flow.specification_id == "soil.phosphorus"
                    else flow
                    for flow in recipe.inputs
                ),
            )
            if recipe.id == "recipe.alfalfa"
            else recipe
            for recipe in region.recipes
        ),
    )
    scenario = grain_first_scenario()
    their_run = run_forward(
        scenario,
        agents=theirs.agents,
        recipes=theirs.recipes,
        standards=theirs.standards,
        compositions=theirs.compositions,
        opening=opening_state(),
    )
    their_export = build_export(
        their_run, scenario, recipes=theirs.recipes, standards=theirs.standards
    )

    result = verify(
        their_export,
        _run(split_scenario()),
        recipes=region.recipes,
        standards=region.standards,
    )
    assert not result.recipes_match
    assert not result.results_match
    assert "disagreement about the world" in result.summary()


def test_divergences_name_the_community_and_period() -> None:
    """Reporting 'they differ' is nearly useless; naming who, when, and by how
    much is what starts a conversation."""
    region = build_reference_region()
    result = verify(
        _export(split_scenario()),
        _run(grain_first_scenario()),
        recipes=region.recipes,
        standards=region.standards,
    )
    assert result.notes
    # The interesting divergence is not in the first year: both allocations
    # give Chakar the same thing in period 0 and separate afterwards.
    assert any("period 1" in note for note in result.notes)
    assert any("chakar" in note for note in result.notes)


def test_export_carries_the_explanation_not_just_the_answer() -> None:
    """'What happened' without 'why' is not something anyone can argue with."""
    export = _export(grain_first_scenario())
    needs = export["results"]["periods"][1]["needs"]
    chakar = next(n for n in needs if n["agent"] == "chakar")
    assert chakar["explanation"]["causes"]


def test_export_records_the_assumptions() -> None:
    export = _export(grain_first_scenario())
    assumptions = " ".join(export["results"]["assumptions"])
    assert "allocation" in assumptions
    assert "transfers are not assumed" in assumptions


def test_exports_are_byte_identical_across_runs() -> None:
    """The property the whole audit right rests on."""
    first = canonical_json(_export(grain_first_scenario()))
    second = canonical_json(_export(grain_first_scenario()))
    assert first == second
