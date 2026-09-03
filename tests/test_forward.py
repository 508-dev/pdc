"""Forward propagation: Liebig, lags, consumption, and explanation."""

from __future__ import annotations

import pytest

from pdc.ontology import Action, Agent, Citation, Provenance, RecipeFlow, RecipeProcess
from pdc.seed import build_reference_region
from pdc.seed.scenarios import (
    CONSUMPTION_STANDARD,
    grain_first_scenario,
    opening_state,
    split_scenario,
)
from pdc.sim import (
    Allocation,
    CauseKind,
    ProcessPlan,
    Scenario,
    WorldState,
    render_text,
    run_forward,
)
from pdc.units import Q

CITATION = Citation("a test", Provenance.ILLUSTRATIVE)


def _region_run(scenario, **overrides):  # type: ignore[no-untyped-def]
    region = build_reference_region()
    kwargs = {
        "agents": region.agents,
        "recipes": region.recipes,
        "standards": region.standards,
        "compositions": region.compositions,
        "opening": opening_state(),
    }
    kwargs.update(overrides)
    return run_forward(scenario, **kwargs)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# Liebig's law of the minimum
# --------------------------------------------------------------------------


def _simple_recipe(phosphorus: float = 10.0, water: float = 100.0) -> RecipeProcess:
    return RecipeProcess(
        "recipe.test",
        "Test crop",
        "grow",
        inputs=(
            RecipeFlow(Action.CONSUME, "soil.phosphorus", Q(phosphorus, "kgP"), CITATION),
            RecipeFlow(Action.CONSUME, "water.irrigation", Q(water, "m^3"), CITATION),
        ),
        outputs=(RecipeFlow(Action.PRODUCE, "wheat.grain", Q(3.0, "tFW"), CITATION),),
    )


def _lone_farm() -> tuple[Agent, ...]:
    return (
        Agent("valley", "Valley", "region"),
        Agent("town", "Town", "commune", member_of="valley", attributes=(("population", 100.0),)),
        Agent("farm", "Farm", "collective", member_of="town"),
    )


def test_output_is_bounded_by_the_scarcest_input() -> None:
    """Liebig: the limiting factor is the answer, not an aggregate score."""
    scenario = Scenario(
        "test",
        Allocation.of(
            "tight-phosphorus",
            {
                ("farm", "soil.phosphorus"): Q(50.0, "kgP"),
                ("farm", "water.irrigation"): Q(10_000.0, "m^3"),
            },
        ),
        (ProcessPlan("farm", "recipe.test", 100.0),),
        periods=1,
    )
    run = _region_run(
        scenario,
        agents=_lone_farm(),
        recipes=(_simple_recipe(),),
        standards=(),
        compositions=(),
        opening=WorldState(),
    )
    outcome = run.period(0).processes[0]
    # 50 kgP at 10 kgP/batch allows 5 batches, though water allows 100.
    assert outcome.achieved_batches == pytest.approx(5.0)
    assert outcome.binding_specification_id == "soil.phosphorus"


def test_the_binding_constraint_is_named_and_quantified() -> None:
    """D-004: the gap is reported in its own units, never as a score."""
    scenario = Scenario(
        "test",
        Allocation.of(
            "tight",
            {
                ("farm", "soil.phosphorus"): Q(50.0, "kgP"),
                ("farm", "water.irrigation"): Q(10_000.0, "m^3"),
            },
        ),
        (ProcessPlan("farm", "recipe.test", 100.0),),
        periods=1,
    )
    run = _region_run(
        scenario,
        agents=_lone_farm(),
        recipes=(_simple_recipe(),),
        standards=(),
        compositions=(),
        opening=WorldState(),
    )
    binding = run.period(0).processes[0].cause.binding_constraints()[0]
    detail = dict(binding.detail)
    assert detail["available"].to("kgP").magnitude == pytest.approx(50.0)
    assert detail["required"].to("kgP").magnitude == pytest.approx(1000.0)


def test_the_binding_constraint_carries_its_citation() -> None:
    """The chain must terminate in a figure someone can dispute by name."""
    scenario = Scenario(
        "test",
        Allocation.of(
            "tight",
            {
                ("farm", "soil.phosphorus"): Q(50.0, "kgP"),
                ("farm", "water.irrigation"): Q(10_000.0, "m^3"),
            },
        ),
        (ProcessPlan("farm", "recipe.test", 100.0),),
        periods=1,
    )
    run = _region_run(
        scenario,
        agents=_lone_farm(),
        recipes=(_simple_recipe(),),
        standards=(),
        compositions=(),
        opening=WorldState(),
    )
    evidence = run.period(0).processes[0].cause.binding_constraints()[0].evidence[0]
    assert evidence.citation.source
    assert evidence.quantity.to("kgP").magnitude == pytest.approx(10.0)


# --------------------------------------------------------------------------
# Lags
# --------------------------------------------------------------------------


def test_lagged_output_arrives_a_period_late() -> None:
    """The alfalfa lag is what makes this a multi-period problem: a single
    period cannot see the consequence of starving next year's feed."""
    lagged = RecipeProcess(
        "recipe.lagged",
        "Lagged crop",
        "grow",
        inputs=(RecipeFlow(Action.CONSUME, "soil.phosphorus", Q(1.0, "kgP"), CITATION),),
        outputs=(RecipeFlow(Action.PRODUCE, "alfalfa", Q(9.0, "tDM"), CITATION, lag_periods=1),),
    )
    scenario = Scenario(
        "test",
        Allocation.of("plenty", {("farm", "soil.phosphorus"): Q(100.0, "kgP")}),
        (ProcessPlan("farm", "recipe.lagged", 10.0),),
        periods=3,
    )
    run = _region_run(
        scenario,
        agents=_lone_farm(),
        recipes=(lagged,),
        standards=(),
        compositions=(),
        opening=WorldState(),
    )
    assert run.period(0).state.held("town", "alfalfa") is None
    assert run.period(1).state.held("town", "alfalfa").to("tDM").magnitude == pytest.approx(90.0)


# --------------------------------------------------------------------------
# Consumption
# --------------------------------------------------------------------------


def test_without_a_consumption_standard_nothing_is_eaten() -> None:
    """Only meaningful for studying production in isolation, and the run says
    so in its assumptions."""
    scenario = Scenario(
        "no-eating", grain_first_scenario().allocation, grain_first_scenario().plans, periods=3
    )
    run = _region_run(scenario)
    assert any("nothing is consumed" in a for a in run.assumptions)
    first = run.period(0).needs[0]
    later = [n for n in run.period(2).needs if n.agent_id == first.agent_id][0]
    assert later.available >= first.available


def test_consumption_standard_must_be_named_not_inferred() -> None:
    """D-006 holds standards to be peers, so PDC must not pick one to drive
    consumption on the user's behalf."""
    assert Scenario("s", Allocation("a"), ()).consumption_standard_id is None


def test_stocks_are_drawn_down_by_what_was_eaten() -> None:
    run = _region_run(grain_first_scenario(periods=3))
    assert any("consumption governed by" in a for a in run.assumptions)
    outcomes = run.needs_for("northsetting", CONSUMPTION_STANDARD)
    # Opening stocks carry the first period; the steady state is lower.
    assert outcomes[1].available < outcomes[0].available


# --------------------------------------------------------------------------
# The reference question
# --------------------------------------------------------------------------


def test_the_two_reference_allocations_give_different_outcomes() -> None:
    grain = _region_run(grain_first_scenario())
    split = _region_run(split_scenario())
    assert grain.scenario_label != split.scenario_label

    def share(run, agent):  # type: ignore[no-untyped-def]
        outcome = run.needs_for(agent, CONSUMPTION_STANDARD)[1]
        return outcome.available.to("kcal").magnitude / outcome.required.to("kcal").magnitude

    assert share(grain, "chakar") != pytest.approx(share(split, "chakar"))


def test_grain_first_starves_chakar_while_split_does_not() -> None:
    """The result that justifies the whole no-scalar-reduction commitment.

    Directing phosphorus to grain yields more food energy valley-wide, and
    leaves Chakar with nothing at all: it has no grain farm, so its only food
    comes through alfalfa and the dairy herd. A single valley-wide figure
    would report the aggregate improvement and hide the community that got
    zero — which is exactly the information D-002 exists to preserve.
    """
    grain = _region_run(grain_first_scenario())
    split = _region_run(split_scenario())

    grain_chakar = grain.needs_for("chakar", CONSUMPTION_STANDARD)[1]
    split_chakar = split.needs_for("chakar", CONSUMPTION_STANDARD)[1]

    assert grain_chakar.available.to("kcal").magnitude == pytest.approx(0.0)
    assert split_chakar.available.to("kcal").magnitude > 0.0
    assert not grain_chakar.met


def test_chakar_shortfall_is_explained_back_to_phosphorus() -> None:
    """Need shortfall -> dairy underrun -> alfalfa shortage -> phosphorus."""
    run = _region_run(grain_first_scenario())
    outcome = [
        o
        for o in run.period(1).needs
        if o.agent_id == "chakar" and o.standard_id == CONSUMPTION_STANDARD
    ][0]

    assert outcome.cause.kind is CauseKind.NEED_SHORTFALL
    kinds = {c.kind for c in outcome.cause.walk()}
    assert CauseKind.PROCESS_UNDERRUN in kinds
    assert CauseKind.BINDING_CONSTRAINT in kinds

    bound_on = {c.subject_id for c in outcome.cause.binding_constraints()}
    assert "soil.phosphorus" in bound_on
    assert "alfalfa" in bound_on


def test_explanations_serialise_for_a_renderer() -> None:
    """A UI reads this tree; it does not recompute from world state. That is
    what stops the screen and the model from drifting apart."""
    run = _region_run(grain_first_scenario())
    outcome = [o for o in run.period(1).needs if o.agent_id == "chakar"][0]
    payload = outcome.cause.to_json()
    assert payload["kind"] == "need_shortfall"
    assert payload["causes"]
    assert payload["detail"][0]["units"]


def test_text_rendering_formats_without_computing() -> None:
    run = _region_run(grain_first_scenario())
    outcome = [o for o in run.period(1).needs if o.agent_id == "chakar"][0]
    text = render_text(outcome.cause)
    assert "limiting factor" in text
    assert "source:" in text


def test_forward_run_reports_no_summary_score() -> None:
    """Reducing 'what happened to this valley' to one number would need
    exchange rates between calories, phosphorus and labour (D-002)."""
    run = _region_run(grain_first_scenario())
    for attribute in ("score", "total", "summary_value", "utility"):
        assert not hasattr(run, attribute)


def test_assumptions_are_stated_on_every_run() -> None:
    run = _region_run(grain_first_scenario())
    joined = " ".join(run.assumptions)
    assert "allocation" in joined
    assert "transfers are not assumed" in joined
    assert "pooled stocks" in joined


def test_runs_are_reproducible() -> None:
    first = _region_run(grain_first_scenario())
    second = _region_run(grain_first_scenario())
    for a, b in zip(first.periods, second.periods, strict=True):
        assert [o.achieved_batches for o in a.processes] == [
            o.achieved_batches for o in b.processes
        ]
        assert [o.available.magnitude for o in a.needs] == [o.available.magnitude for o in b.needs]


def test_an_input_with_no_allocation_binds_at_zero() -> None:
    """An ungranted input is not an unlimited one. Treating a missing
    allocation as plenty would let a scenario quietly conjure resources."""
    scenario = Scenario(
        "no-water",
        Allocation.of("phosphorus-only", {("farm", "soil.phosphorus"): Q(50.0, "kgP")}),
        (ProcessPlan("farm", "recipe.test", 100.0),),
        periods=1,
    )
    run = _region_run(
        scenario,
        agents=_lone_farm(),
        recipes=(_simple_recipe(),),
        standards=(),
        compositions=(),
        opening=WorldState(),
    )
    outcome = run.period(0).processes[0]
    assert outcome.achieved_batches == pytest.approx(0.0)
    assert outcome.binding_specification_id == "water.irrigation"
