"""Views.

These format kernel objects. They compute nothing — every figure on screen
comes from `pdc.analysis`, `pdc.sim`, or `pdc.needs`, so the interface cannot
disagree with the model or with the CLI (D-010).
"""

from __future__ import annotations

from typing import Any

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from pdc.analysis import resource_pressure
from pdc.seed.scenarios import CONSUMPTION_STANDARD, whole_valley_batches
from pdc.web.context import SCENARIOS, readings, region, run


def _standard_id(request: HttpRequest) -> str:
    world = region()
    requested = request.GET.get("standard", CONSUMPTION_STANDARD)
    if not any(standard.id == requested for standard in world.standards):
        raise Http404(f"no standard {requested!r}")
    return requested


def overview(request: HttpRequest) -> HttpResponse:
    """The world as it stands: who is here, what they hold, what they require."""
    world = region()
    standard_id = _standard_id(request)

    communities = []
    for agent in sorted((a for a in world.agents if a.kind == "commune"), key=lambda a: a.name):
        per_standard = [
            {
                "standard": standard,
                "per_day": standard.evaluate(agent).to("kcal/day"),
            }
            for standard in sorted(world.standards, key=lambda s: s.id)
            if all(agent.has_attribute(path) for path in standard.requires)
        ]
        communities.append(
            {
                "agent": agent,
                "population": agent.attribute("population"),
                "members": world.members_of(agent.id),
                "needs": per_standard,
            }
        )

    stock = next(r for r in world.resources if r.specification_id == "soil.phosphorus")
    pressure = resource_pressure(
        "soil.phosphorus", stock.quantity, world.recipes, whole_valley_batches(world)
    )
    demands = [
        {"demand": demand, "ratio": demand.ratio_of(pressure.available)}
        for demand in pressure.demands
    ]

    return render(
        request,
        "pdc/overview.html",
        {
            "communities": communities,
            "resources": world.resources,
            "pressure": pressure,
            "demands": demands,
            "standards": sorted(world.standards, key=lambda s: s.id),
            "standard_id": standard_id,
        },
    )


def compare(request: HttpRequest) -> HttpResponse:
    """Two allocations, side by side. No verdict, and no aggregate row."""
    standard_id = _standard_id(request)
    world = region()

    tables = {name: readings(name, standard_id) for name in SCENARIOS}
    runs = {name: run(name) for name in SCENARIOS}

    rows = []
    for agent in sorted((a for a in world.agents if a.kind == "commune"), key=lambda a: a.name):
        rows.append(
            {
                "agent": agent,
                "columns": [
                    {"scenario": name, "readings": tables[name][agent.id]} for name in SCENARIOS
                ],
            }
        )

    return render(
        request,
        "pdc/compare.html",
        {
            "rows": rows,
            "scenarios": SCENARIOS,
            "runs": runs,
            "standard_id": standard_id,
            "standards": sorted(world.standards, key=lambda s: s.id),
        },
    )


def _cause_context(cause: Any, depth: int = 0) -> dict[str, Any]:
    """Flatten a Cause tree for the template.

    Django's template language has no recursion, so the walk happens here.
    Note it only reshapes — the tree came from the kernel and no number in it
    is recomputed.
    """
    return {
        "cause": cause,
        "depth": depth,
        "kind": cause.kind.value,
        "detail": cause.detail,
        "evidence": cause.evidence,
        "children": [_cause_context(child, depth + 1) for child in cause.causes],
    }


def explain(request: HttpRequest, scenario: str, agent_id: str, period: int) -> HttpResponse:
    """Why a community ended up where it did, down to the cited coefficient.

    The chain terminates in a figure and its source, so someone who disagrees
    has something specific to disagree with.
    """
    if scenario not in SCENARIOS:
        raise Http404(f"no scenario {scenario!r}")

    standard_id = _standard_id(request)
    forward = run(scenario)

    if period >= len(forward.periods):
        raise Http404(f"no period {period}")

    matches = [
        outcome
        for outcome in forward.period(period).needs
        if outcome.agent_id == agent_id and outcome.standard_id == standard_id
    ]
    if not matches:
        raise Http404(f"no reading for {agent_id!r} in period {period}")

    outcome = matches[0]
    world = region()
    agent = world.agent(agent_id)

    return render(
        request,
        "pdc/explain.html",
        {
            "outcome": outcome,
            "agent": agent,
            "scenario": scenario,
            "period": period,
            "periods": range(len(forward.periods)),
            "tree": _cause_context(outcome.cause),
            "assumptions": forward.assumptions,
            "standard_id": standard_id,
        },
    )
