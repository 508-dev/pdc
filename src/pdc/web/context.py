"""Building the world the explorer shows.

Every view goes through here so that the interface and the CLI are looking at
the same kernel objects. Views format; they do not compute.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from pdc.seed import Region, build_reference_region
from pdc.seed.scenarios import grain_first_scenario, opening_state, split_scenario
from pdc.sim import ForwardRun, Scenario, run_forward

SCENARIOS = ("grain-first", "split")


@lru_cache(maxsize=1)
def region() -> Region:
    """The world. Cached because building it is pure and deterministic.

    Safe to cache for exactly that reason: it reads no clock, no environment,
    and no filesystem, so the same call always yields the same value.
    """
    return build_reference_region()


def scenario_for(name: str, periods: int = 3) -> Scenario:
    if name not in SCENARIOS:
        raise ValueError(f"unknown scenario {name!r}")
    return grain_first_scenario(periods) if name == "grain-first" else split_scenario(periods)


@lru_cache(maxsize=32)
def run(name: str, periods: int = 3) -> ForwardRun:
    scenario = scenario_for(name, periods)
    world = region()
    return run_forward(
        scenario,
        agents=world.agents,
        recipes=world.recipes,
        standards=world.standards,
        compositions=world.compositions,
        opening=opening_state(),
    )


@dataclass(frozen=True, slots=True)
class Reading:
    """One community measured against one standard, ready to display."""

    agent_id: str
    agent_name: str
    standard_id: str
    period: int
    available: object
    required: object
    percentage: float
    met: bool

    @property
    def is_destitute(self) -> bool:
        """Nothing at all, which a percentage alone reads past too easily."""
        return self.percentage <= 0.0


def readings(name: str, standard_id: str, periods: int = 3) -> dict[str, list[Reading]]:
    """Per community, per period, as percentages of that community's standard.

    Percentages are of each community's own declared standard and are never
    summed across communities. One allocation can be better in aggregate while
    leaving a community with nothing, and a single figure would hide that
    (D-002).
    """
    world = region()
    forward = run(name, periods)
    names = {agent.id: agent.name for agent in world.agents}

    out: dict[str, list[Reading]] = {}
    for agent in sorted((a for a in world.agents if a.kind == "commune"), key=lambda a: a.name):
        rows: list[Reading] = []
        for outcome in forward.needs_for(agent.id, standard_id):
            required = outcome.required.to("kcal").magnitude
            available = outcome.available.to("kcal").magnitude
            rows.append(
                Reading(
                    agent_id=agent.id,
                    agent_name=names.get(agent.id, agent.id),
                    standard_id=standard_id,
                    period=outcome.period,
                    available=outcome.available,
                    required=outcome.required,
                    percentage=(100.0 * available / required) if required else 0.0,
                    met=outcome.met,
                )
            )
        out[agent.id] = rows
    return out
