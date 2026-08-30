"""The synthetic reference region.

A small mixed-farming valley: four communities, six farms, a dairy, a mill and
a bakery, with a phosphorus stock and a watershed as ecosystem agents. Place
names are from Le Guin's Anarres.

It exists to be the fixture the reference question is asked of:

    Direct all available phosphorus to one farm, or split it. Run forward
    three years with the alfalfa-to-cattle lag. Report the calorie outcome per
    community per year against each community's declared need standards.

Everything here is built from ``pdc.seed.coefficients``, and nearly all of
those are marked ILLUSTRATIVE. This is a demonstration region, not a claim
about any real place.
"""

from __future__ import annotations

from dataclasses import dataclass

from pdc.needs import Attr, BinOp, Lit, NeedStandard
from pdc.ontology import (
    Action,
    Agent,
    Citation,
    EconomicResource,
    ProcessSpecification,
    Provenance,
    RecipeFlow,
    RecipeProcess,
    ResourceSpecification,
)
from pdc.seed import coefficients as C
from pdc.units import Q


@dataclass(frozen=True, slots=True)
class Region:
    """A complete world definition, before any simulation has been run."""

    agents: tuple[Agent, ...]
    resource_specifications: tuple[ResourceSpecification, ...]
    process_specifications: tuple[ProcessSpecification, ...]
    recipes: tuple[RecipeProcess, ...]
    resources: tuple[EconomicResource, ...]
    standards: tuple[NeedStandard, ...]

    def agent(self, agent_id: str) -> Agent:
        for agent in self.agents:
            if agent.id == agent_id:
                return agent
        raise KeyError(f"no agent {agent_id!r} in region")

    def members_of(self, agent_id: str) -> tuple[Agent, ...]:
        """Direct children in the agent tree (D-009)."""
        return tuple(a for a in self.agents if a.member_of == agent_id)

    def descendants_of(self, agent_id: str) -> tuple[Agent, ...]:
        """All agents below this one, at any depth.

        Aggregation over a branch of the tree is one traversal with a depth
        argument rather than a separate subsystem — which is what makes
        federation later a query rather than a rewrite.
        """
        found: list[Agent] = []
        frontier = [agent_id]
        while frontier:
            current = frontier.pop()
            for child in self.members_of(current):
                found.append(child)
                frontier.append(child.id)
        return tuple(sorted(found, key=lambda a: a.id))

    def standard(self, standard_id: str) -> NeedStandard:
        for standard in self.standards:
            if standard.id == standard_id:
                return standard
        raise KeyError(f"no standard {standard_id!r} in region")


# --------------------------------------------------------------------------
# Resource and process specifications
# --------------------------------------------------------------------------


def _resource_specifications() -> tuple[ResourceSpecification, ...]:
    return (
        ResourceSpecification("wheat.grain", "Wheat grain", "tFW"),
        ResourceSpecification("wheat.flour", "Wheat flour", "tFW"),
        ResourceSpecification("bread", "Bread", "tFW"),
        ResourceSpecification("potato", "Potatoes", "tFW"),
        ResourceSpecification("alfalfa", "Alfalfa (dry matter)", "tDM"),
        ResourceSpecification("milk", "Milk", "tFW"),
        ResourceSpecification("soil.phosphorus", "Soil phosphorus", "kgP", is_ecosystem_stock=True),
        ResourceSpecification(
            "water.irrigation", "Irrigation water", "m^3", is_ecosystem_stock=True
        ),
        ResourceSpecification("land.arable", "Arable land", "ha_season"),
        ResourceSpecification("labour.field", "Field labour", "labour_hour", is_labour=True),
        ResourceSpecification("labour.mill", "Milling labour", "labour_hour", is_labour=True),
        ResourceSpecification("labour.bake", "Baking labour", "labour_hour", is_labour=True),
        ResourceSpecification("labour.dairy", "Dairy labour", "labour_hour", is_labour=True),
        ResourceSpecification("food.energy", "Food energy", "kcal"),
    )


def _process_specifications() -> tuple[ProcessSpecification, ...]:
    return (
        ProcessSpecification("grow.wheat", "Growing wheat"),
        ProcessSpecification("grow.potato", "Growing potatoes"),
        ProcessSpecification("grow.alfalfa", "Growing alfalfa"),
        ProcessSpecification("milk.cattle", "Dairying"),
        ProcessSpecification("mill.grain", "Milling grain"),
        ProcessSpecification("bake.bread", "Baking bread"),
    )


# --------------------------------------------------------------------------
# Recipes
#
# Coefficients are per hectare-season, so a recipe's batch is one hectare of
# one crop for one season. Planning scales them.
# --------------------------------------------------------------------------


def _crop_recipe(
    recipe_id: str,
    name: str,
    process_id: str,
    output_spec: str,
    yield_c: object,
    p_removal_c: object,
    water_c: object,
    labour_c: object,
    output_lag: int = 0,
) -> RecipeProcess:
    """One hectare-season of a crop.

    Phosphorus is modelled as consumed from the soil stock in proportion to
    what the harvest removes, so a soil agent's balance falls as it is cropped
    and the deficit shows up in later seasons.
    """
    # Coefficients are per hectare-season and the batch is one hectare-season,
    # so each is multiplied through by the batch area. The registry will not
    # let a per-hectare rate masquerade as a quantity.
    batch = Q(1.0, "ha_season")
    yield_per_batch = yield_c.value * batch  # type: ignore[attr-defined]
    removal = p_removal_c.value * yield_per_batch  # type: ignore[attr-defined]

    return RecipeProcess(
        id=recipe_id,
        name=name,
        process_specification_id=process_id,
        inputs=(
            RecipeFlow(Action.USE, "land.arable", batch, C.FIXTURE),
            RecipeFlow(
                Action.CONSUME,
                "soil.phosphorus",
                removal.to("kgP"),
                p_removal_c.citation,  # type: ignore[attr-defined]
            ),
            RecipeFlow(
                Action.CONSUME,
                "water.irrigation",
                (water_c.value * batch).to("m^3"),  # type: ignore[attr-defined]
                water_c.citation,  # type: ignore[attr-defined]
            ),
            RecipeFlow(
                Action.WORK,
                "labour.field",
                (labour_c.value * batch).to("labour_hour"),  # type: ignore[attr-defined]
                labour_c.citation,  # type: ignore[attr-defined]
            ),
        ),
        outputs=(
            RecipeFlow(
                Action.PRODUCE,
                output_spec,
                yield_per_batch,
                yield_c.citation,  # type: ignore[attr-defined]
                lag_periods=output_lag,
            ),
        ),
    )


def _recipes() -> tuple[RecipeProcess, ...]:
    wheat = _crop_recipe(
        "recipe.wheat",
        "Wheat, one hectare-season",
        "grow.wheat",
        "wheat.grain",
        C.WHEAT_YIELD,
        C.WHEAT_P_REMOVAL,
        C.WHEAT_WATER,
        C.WHEAT_LABOUR,
    )
    potato = _crop_recipe(
        "recipe.potato",
        "Potatoes, one hectare-season",
        "grow.potato",
        "potato",
        C.POTATO_YIELD,
        C.POTATO_P_REMOVAL,
        C.POTATO_WATER,
        C.POTATO_LABOUR,
    )
    alfalfa = _crop_recipe(
        "recipe.alfalfa",
        "Alfalfa, one hectare-season",
        "grow.alfalfa",
        "alfalfa",
        C.ALFALFA_YIELD,
        C.ALFALFA_P_REMOVAL,
        C.ALFALFA_WATER,
        C.ALFALFA_LABOUR,
        # The lag that makes this a multi-period problem: alfalfa cut this
        # season is fed to cattle in the next one. A single-period model cannot
        # see the consequence of starving the alfalfa crop of phosphorus.
        output_lag=1,
    )

    # The dairy coefficients are annual rates, and the recipe batch is one
    # cow-year, so each is multiplied by the batch duration to give a
    # per-batch quantity. Writing that out rather than dropping the `/year`
    # keeps the units honest: the registry rejects the shortcut.
    cow_year = Q(1.0, "year")
    dairy = RecipeProcess(
        id="recipe.dairy",
        name="Dairying, one cow-year",
        process_specification_id="milk.cattle",
        inputs=(
            RecipeFlow(
                Action.CONSUME,
                "alfalfa",
                (C.COW_FEED.value * C.COW_ALFALFA_FRACTION.value * cow_year).to("tDM"),
                C.COW_FEED.citation,
            ),
            RecipeFlow(
                Action.WORK,
                "labour.dairy",
                (C.DAIRY_LABOUR.value * cow_year).to("labour_hour"),
                C.DAIRY_LABOUR.citation,
            ),
        ),
        outputs=(
            RecipeFlow(
                Action.PRODUCE,
                "milk",
                (C.MILK_YIELD.value * cow_year).to("tFW"),
                C.MILK_YIELD.citation,
            ),
        ),
    )

    mill = RecipeProcess(
        id="recipe.mill",
        name="Milling, one tonne of grain",
        process_specification_id="mill.grain",
        inputs=(
            RecipeFlow(Action.CONSUME, "wheat.grain", Q(1.0, "tFW"), C.FIXTURE),
            RecipeFlow(
                Action.WORK,
                "labour.mill",
                C.MILL_LABOUR.value * Q(1.0, "tFW"),
                C.MILL_LABOUR.citation,
            ),
        ),
        outputs=(
            RecipeFlow(
                Action.PRODUCE,
                "wheat.flour",
                (C.FLOUR_EXTRACTION.value * Q(1.0, "tFW")).to("tFW"),
                C.FLOUR_EXTRACTION.citation,
            ),
        ),
    )

    bakery = RecipeProcess(
        id="recipe.bakery",
        name="Baking, one tonne of flour",
        process_specification_id="bake.bread",
        inputs=(
            RecipeFlow(Action.CONSUME, "wheat.flour", Q(1.0, "tFW"), C.FIXTURE),
            RecipeFlow(Action.WORK, "labour.bake", Q(12.0, "labour_hour"), C.BAKE_LABOUR.citation),
        ),
        outputs=(
            RecipeFlow(
                Action.PRODUCE,
                "bread",
                (C.BREAD_YIELD.value * Q(1.0, "tFW")).to("tFW"),
                C.BREAD_YIELD.citation,
            ),
        ),
    )

    return (wheat, potato, alfalfa, dairy, mill, bakery)


# --------------------------------------------------------------------------
# Agents
# --------------------------------------------------------------------------


def _agents() -> tuple[Agent, ...]:
    valley = Agent("abbenay-valley", "Abbenay Valley", "region")

    communities = (
        Agent(
            "northsetting",
            "Northsetting",
            "commune",
            member_of="abbenay-valley",
            attributes=(("population", 12000.0), ("climate.mean_temp_c", 11.5)),
        ),
        Agent(
            "chakar",
            "Chakar",
            "commune",
            member_of="abbenay-valley",
            attributes=(("population", 4500.0), ("climate.mean_temp_c", 12.0)),
        ),
        Agent(
            "red-springs",
            "Red Springs",
            "commune",
            member_of="abbenay-valley",
            attributes=(("population", 2800.0), ("climate.mean_temp_c", 13.2)),
        ),
        Agent(
            "round-valley",
            "Round Valley",
            "commune",
            member_of="abbenay-valley",
            attributes=(("population", 6700.0), ("climate.mean_temp_c", 10.8)),
        ),
    )

    # Farms A and B are the two the reference question puts in competition:
    # A grows wheat (calories now), B grows alfalfa (calories next year, via
    # the ranches). Both draw on the same phosphorus stock.
    farms = (
        Agent(
            "farm-a",
            "Farm A (wheat, Northsetting)",
            "collective",
            member_of="northsetting",
            attributes=(("land.arable_ha", 900.0),),
        ),
        Agent(
            "farm-b",
            "Farm B (alfalfa, Chakar)",
            "collective",
            member_of="chakar",
            attributes=(("land.arable_ha", 600.0),),
        ),
        Agent(
            "farm-c",
            "Farm C (wheat, Round Valley)",
            "collective",
            member_of="round-valley",
            attributes=(("land.arable_ha", 700.0),),
        ),
        Agent(
            "farm-d",
            "Farm D (potatoes, Northsetting)",
            "collective",
            member_of="northsetting",
            attributes=(("land.arable_ha", 250.0),),
        ),
        Agent(
            "farm-e",
            "Farm E (mixed, Red Springs)",
            "collective",
            member_of="red-springs",
            attributes=(("land.arable_ha", 320.0),),
        ),
        Agent(
            "farm-f",
            "Farm F (alfalfa, Round Valley)",
            "collective",
            member_of="round-valley",
            attributes=(("land.arable_ha", 480.0),),
        ),
    )

    ranches = (
        Agent(
            "ranch-c",
            "Ranch C (dairy, Chakar)",
            "collective",
            member_of="chakar",
            attributes=(("herd.cows", 400.0),),
        ),
        Agent(
            "ranch-d",
            "Ranch D (dairy, Round Valley)",
            "collective",
            member_of="round-valley",
            attributes=(("herd.cows", 320.0),),
        ),
    )

    workshops = (
        Agent("mill-north", "Northsetting Mill", "collective", member_of="northsetting"),
        Agent("bakery-north", "Northsetting Bakery", "collective", member_of="northsetting"),
    )

    # Ecosystem agents. Valueflows explicitly sanctions this, so soil
    # phosphorus drawdown needs no special case: the soil holds a stock and
    # cropping decrements it, exactly like a granary.
    ecosystems = (
        Agent("soil-valley", "Abbenay Valley soils", "ecosystem", member_of="abbenay-valley"),
        Agent("watershed", "Abbenay watershed", "ecosystem", member_of="abbenay-valley"),
    )

    return (valley, *communities, *farms, *ranches, *workshops, *ecosystems)


# --------------------------------------------------------------------------
# Opening balances
# --------------------------------------------------------------------------


def _resources() -> tuple[EconomicResource, ...]:
    """Opening stocks.

    Phosphorus is deliberately scarce: less than the valley would need to crop
    everything it could otherwise crop. That scarcity is the whole point of
    the fixture — with enough phosphorus for everyone there is no allocation
    question and nothing to argue about.
    """
    return (
        EconomicResource("stock.p", "soil.phosphorus", "soil-valley", Q(11_000.0, "kgP")),
        EconomicResource("stock.water", "water.irrigation", "watershed", Q(9_500_000.0, "m^3")),
        EconomicResource("stock.grain.north", "wheat.grain", "northsetting", Q(900.0, "tFW")),
        EconomicResource("stock.potato.north", "potato", "northsetting", Q(300.0, "tFW")),
        EconomicResource("stock.alfalfa.chakar", "alfalfa", "chakar", Q(400.0, "tDM")),
    )


# --------------------------------------------------------------------------
# Need standards
# --------------------------------------------------------------------------


def _standards() -> tuple[NeedStandard, ...]:
    """Two standards, published as peers.

    There is no ladder here and no privileged standard (D-006). These are two
    claims about food energy from two different authors with two different
    citations. A community declares which it wants to be evaluated against,
    and the system reports state against each. Calling one of them 'the'
    requirement is a political act, not a schema feature.
    """
    sphere = NeedStandard(
        id="sphere-2018:food-energy",
        name="Sphere minimum food energy",
        author_id="sphere-project",
        citation=C.SPHERE,
        version="2018.1",
        expression=BinOp("mul", Attr("population"), Lit(2100.0, "kcal/day")),
        produces_specification_id="food.energy",
        requires=("population",),
        applies_to="A general population in a crisis or hard period.",
    )

    valley = NeedStandard(
        id="abbenay-valley:food-energy-adequate",
        name="Abbenay Valley adequate food energy",
        author_id="abbenay-valley",
        citation=Citation(
            source="Abbenay Valley federation, recorded deliberation of 2027",
            provenance=Provenance.DELIBERATED,
            note=(
                "Agreed as an ordinary-life intake for a mixed-activity "
                "population, not a survival minimum. A worked example of a "
                "community publishing its own standard rather than adopting "
                "an external one."
            ),
        ),
        version="2027.1",
        expression=BinOp("mul", Attr("population"), Lit(2500.0, "kcal/day")),
        produces_specification_id="food.energy",
        requires=("population",),
        applies_to="Communities of the Abbenay Valley federation.",
    )

    return (sphere, valley)


def build_reference_region() -> Region:
    """Construct the synthetic reference region.

    Pure and deterministic: no clock, no randomness, no I/O. Calling it twice
    yields equal values.
    """
    return Region(
        agents=_agents(),
        resource_specifications=_resource_specifications(),
        process_specifications=_process_specifications(),
        recipes=_recipes(),
        resources=_resources(),
        standards=_standards(),
    )
