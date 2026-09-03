"""The reference scenarios.

Two ways of dividing a scarce phosphorus stock, put side by side. This is the
question the whole project was built to answer, and the answer PDC gives is
deliberately not "do this one" — it is two sets of physical outcomes and the
chain of consequence that produced each.

    The valley holds 11,000 kg of phosphorus. Sowing everything the farms
    could sow would take roughly 47,000 kg. So something gives, and which
    thing gives is a decision for the people of the valley.

Both allocations below are *inputs*. PDC did not derive them and cannot rank
them (D-001, D-004).
"""

from __future__ import annotations

from pdc.sim.world import Allocation, ProcessPlan, Scenario, WorldState
from pdc.units import Q

# Farms and their intended scale, in hectares. Ranches in head of cattle.
WHEAT_FARMS: tuple[tuple[str, float], ...] = (
    ("farm-a", 900.0),
    ("farm-c", 700.0),
    ("farm-e", 320.0),
)
ALFALFA_FARMS: tuple[tuple[str, float], ...] = (
    ("farm-b", 600.0),
    ("farm-f", 480.0),
)
POTATO_FARMS: tuple[tuple[str, float], ...] = (("farm-d", 250.0),)
RANCHES: tuple[tuple[str, float], ...] = (("ranch-c", 400.0), ("ranch-d", 320.0))

PHOSPHORUS_STOCK = Q(11_000.0, "kgP")


def reference_plans() -> tuple[ProcessPlan, ...]:
    """What everyone intends to do, every period.

    Intentions, not promises. Forward propagation reports what each would
    actually achieve given what is available, which is usually less.
    """
    plans = [
        *(ProcessPlan(agent, "recipe.wheat", area) for agent, area in WHEAT_FARMS),
        *(ProcessPlan(agent, "recipe.alfalfa", area) for agent, area in ALFALFA_FARMS),
        *(ProcessPlan(agent, "recipe.potato", area) for agent, area in POTATO_FARMS),
        *(ProcessPlan(agent, "recipe.dairy", herd) for agent, herd in RANCHES),
        # Northsetting mills and bakes some of its grain. Milling to white
        # flour loses food energy — the bran goes, water comes in — so this is
        # a choice about palatability and storage, not a free gain.
        ProcessPlan("mill-north", "recipe.mill", 600.0),
        ProcessPlan("bakery-north", "recipe.bakery", 400.0),
    ]
    return tuple(sorted(plans, key=lambda p: (p.agent_id, p.recipe_id)))


def opening_state() -> WorldState:
    """Opening stocks, held at the community that holds them."""
    return WorldState.of(
        0,
        {
            ("northsetting", "wheat.grain"): Q(900.0, "tFW"),
            ("northsetting", "potato"): Q(300.0, "tFW"),
            ("chakar", "alfalfa"): Q(400.0, "tDM"),
            ("watershed", "water.irrigation"): Q(9_500_000.0, "m^3"),
        },
    )


def _water_grant() -> dict[tuple[str, str], object]:
    """Irrigation water, granted generously so that phosphorus is the
    constraint under study. A scenario that wanted to study water would
    tighten this instead."""
    farms = [*WHEAT_FARMS, *ALFALFA_FARMS, *POTATO_FARMS]
    return {(agent, "water.irrigation"): Q(20_000_000.0, "m^3") for agent, _ in farms}


def _land_grant() -> dict[tuple[str, str], object]:
    farms = [*WHEAT_FARMS, *ALFALFA_FARMS, *POTATO_FARMS]
    return {(agent, "land.arable"): Q(area, "ha_season") for agent, area in farms}


def grain_first_allocation() -> Allocation:
    """All phosphorus to the grain and potato farms.

    Maximises food energy in the first year. The alfalfa farms get nothing, so
    the dairy herds lose their feed the year after — which is the consequence
    this scenario exists to make visible.
    """
    grain_hectares = sum(area for _, area in WHEAT_FARMS)
    potato_hectares = sum(area for _, area in POTATO_FARMS)
    total = grain_hectares + potato_hectares

    shares: dict[tuple[str, str], object] = {}
    for agent, area in [*WHEAT_FARMS, *POTATO_FARMS]:
        shares[(agent, "soil.phosphorus")] = PHOSPHORUS_STOCK * (area / total)
    for agent, _ in ALFALFA_FARMS:
        shares[(agent, "soil.phosphorus")] = Q(0.0, "kgP")

    shares.update(_water_grant())
    shares.update(_land_grant())
    return Allocation.of("grain-first", shares)  # type: ignore[arg-type]


def split_allocation(alfalfa_share: float = 0.4) -> Allocation:
    """Phosphorus divided between grain and forage.

    Less food energy in year one, because grain gets less. More in later
    years, because the herds keep producing. The trade is across time, and
    there is no exchange rate between this year's calories and next year's
    that PDC could apply on anyone's behalf.
    """
    if not 0.0 <= alfalfa_share <= 1.0:
        raise ValueError(f"alfalfa share must be in [0, 1], got {alfalfa_share}")

    to_alfalfa = PHOSPHORUS_STOCK * alfalfa_share
    to_grain = PHOSPHORUS_STOCK * (1.0 - alfalfa_share)

    grain_farms = [*WHEAT_FARMS, *POTATO_FARMS]
    grain_hectares = sum(area for _, area in grain_farms)
    alfalfa_hectares = sum(area for _, area in ALFALFA_FARMS)

    shares: dict[tuple[str, str], object] = {}
    for agent, area in grain_farms:
        shares[(agent, "soil.phosphorus")] = to_grain * (area / grain_hectares)
    for agent, area in ALFALFA_FARMS:
        shares[(agent, "soil.phosphorus")] = to_alfalfa * (area / alfalfa_hectares)

    shares.update(_water_grant())
    shares.update(_land_grant())
    return Allocation.of(f"split-{alfalfa_share:g}", shares)  # type: ignore[arg-type]


CONSUMPTION_STANDARD = "abbenay-valley:food-energy-adequate"
"""Which standard drives how much people eat.

Named explicitly rather than inferred. The valley's own deliberated standard
is used because it is the one its communities agreed describes ordinary life;
the Sphere minimum is still evaluated alongside, as a separate reading.
"""


def grain_first_scenario(periods: int = 3) -> Scenario:
    return Scenario(
        "grain-first",
        grain_first_allocation(),
        reference_plans(),
        periods,
        consumption_standard_id=CONSUMPTION_STANDARD,
    )


def split_scenario(periods: int = 3, alfalfa_share: float = 0.4) -> Scenario:
    return Scenario(
        f"split-{alfalfa_share:g}",
        split_allocation(alfalfa_share),
        reference_plans(),
        periods,
        consumption_standard_id=CONSUMPTION_STANDARD,
    )
