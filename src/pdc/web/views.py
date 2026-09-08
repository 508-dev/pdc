"""Views.

These format kernel objects. They compute nothing — every figure on screen
comes from `pdc.analysis`, `pdc.sim`, or `pdc.needs`, so the interface cannot
disagree with the model or with the CLI (D-010).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import render

from pdc.analysis import resource_pressure
from pdc.seed.scenarios import CONSUMPTION_STANDARD, whole_valley_batches
from pdc.sim import diff_recipes, is_diffable, verify
from pdc.web.context import (
    SCENARIOS,
    readings,
    readings_from_run,
    region,
    run,
    run_scenario,
)
from pdc.web.params import NO_CONSUMPTION, ExploreParams, ParameterError


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


VENDOR = Path(__file__).resolve().parent / "vendor"


def htmx_script(request: HttpRequest) -> HttpResponse:
    """Serve the vendored copy of HTMX.

    Vendored rather than loaded from a CDN: a tool a syndicate self-hosts
    should not depend on someone else's uptime, someone else's logs, or a
    working route to the wider internet.
    """
    return HttpResponse(
        (VENDOR / "htmx.min.js").read_bytes(),
        content_type="application/javascript",
        headers={"Cache-Control": "public, max-age=86400"},
    )


def _explore_context(params: ExploreParams) -> dict[str, Any]:
    world = region()
    scenario = params.to_scenario()
    branch = params.to_branch()
    forward = run_scenario(scenario)

    standard_id = params.standard_id
    rows = []
    if standard_id is not None:
        table = readings_from_run(forward, standard_id)
        for agent in sorted((a for a in world.agents if a.kind == "commune"), key=lambda a: a.name):
            rows.append({"agent": agent, "readings": table[agent.id]})

    return {
        "params": params,
        "branch": branch,
        "branch_digest": branch.digest,
        "scenario": scenario,
        "run": forward,
        "rows": rows,
        "periods": range(params.periods),
        "standards": sorted(world.standards, key=lambda s: s.id),
        "standard_id": standard_id,
        "no_consumption": NO_CONSUMPTION,
        "query": params.to_query(),
    }


def explore(request: HttpRequest) -> HttpResponse:
    """Move an assumption, see what follows.

    The page and the fragment render from the same context, so the view a
    reader reaches by dragging the slider is identical to the one they reach
    by pasting the URL. Without that, a shared link would show something
    subtly different from what the sharer saw.
    """
    world = region()
    try:
        params = ExploreParams.parse(
            request.GET.dict(), {standard.id for standard in world.standards}
        )
    except ParameterError as error:
        return HttpResponseBadRequest(f"{error}")

    context = _explore_context(params)
    template = "pdc/_results.html" if request.headers.get("HX-Request") else "pdc/explore.html"
    return render(request, template, context)


def coefficients(request: HttpRequest) -> HttpResponse:
    """Every coefficient the model runs on, with where it came from.

    The numbers are the argument. Putting all of them on one page, with their
    provenance visible, is what lets someone say "that one is wrong for our
    soil" instead of disputing a conclusion they cannot get behind.
    """
    world = region()
    rows = []
    for recipe in sorted(world.recipes, key=lambda r: r.id):
        for flow in recipe.flows():
            rows.append(
                {
                    "recipe": recipe,
                    "flow": flow,
                    "is_illustrative": flow.citation.provenance.value == "illustrative",
                }
            )

    illustrative = sum(1 for row in rows if row["is_illustrative"])
    return render(
        request,
        "pdc/coefficients.html",
        {
            "rows": rows,
            "illustrative": illustrative,
            "total": len(rows),
            "standards": sorted(world.standards, key=lambda s: s.id),
        },
    )


def compare_models(request: HttpRequest) -> HttpResponse:
    """Upload someone else's export and find out where you disagree.

    Two findings, kept apart because collapsing them hides the interesting
    one: your code differs from theirs, or you believe different things about
    the world. The second is not a fault, and the page says so.
    """
    world = region()
    context: dict[str, Any] = {"max_bytes": settings.MAX_UPLOAD_BYTES}

    if request.method != "POST":
        return render(request, "pdc/compare_models.html", context)

    upload = request.FILES.get("export")
    if upload is None:
        context["error"] = "Choose an export file to compare against."
        return render(request, "pdc/compare_models.html", context, status=400)

    if upload.size and upload.size > settings.MAX_UPLOAD_BYTES:
        context["error"] = "That file is larger than this page accepts."
        return render(request, "pdc/compare_models.html", context, status=400)

    try:
        document = json.loads(upload.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        context["error"] = f"That does not parse as a PDC export: {error}"
        return render(request, "pdc/compare_models.html", context, status=400)

    if not isinstance(document, dict) or "results" not in document:
        context["error"] = "That JSON is not a PDC export — it has no results."
        return render(request, "pdc/compare_models.html", context, status=400)

    label = document.get("scenario", {}).get("label", "")
    name = "grain-first" if str(label).startswith("grain") else "split"
    periods = document.get("scenario", {}).get("periods", 3)

    forward = run(name, periods)
    result = verify(document, forward, recipes=world.recipes, standards=world.standards)
    differences = diff_recipes(document, world.recipes) if is_diffable(document) else ()

    context.update(
        {
            "filename": upload.name,
            "document": document,
            "verification": result,
            "differences": differences,
            "diffable": is_diffable(document),
            "their_scenario": label,
            "compared_against": name,
        }
    )
    return render(request, "pdc/compare_models.html", context)
