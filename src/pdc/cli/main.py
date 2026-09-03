"""Command-line shell.

A shell, not the kernel. Nothing under ``pdc.units``, ``pdc.ontology``,
``pdc.needs``, or ``pdc.seed`` may import from here.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections.abc import Sequence

from pdc.costing import rollup
from pdc.needs import to_json
from pdc.ontology import Action
from pdc.seed import Region, build_reference_region
from pdc.seed import coefficients as coefficients_module
from pdc.seed.scenarios import (
    CONSUMPTION_STANDARD,
    grain_first_scenario,
    opening_state,
    split_scenario,
)
from pdc.sim import (
    Assumption,
    AssumptionKind,
    Branch,
    ForwardRun,
    build_export,
    render_text,
    run_forward,
    short,
    verify,
)
from pdc.units import Q


def _print_region(region: Region) -> None:
    print("Abbenay Valley — synthetic reference region")
    print("=" * 62)
    print()

    print("Agents")
    print("-" * 62)
    for agent in sorted(region.agents, key=lambda a: (a.member_of or "", a.id)):
        indent = "  " if agent.member_of else ""
        attrs = ", ".join(f"{k}={v:g}" for k, v in agent.attributes)
        suffix = f"  [{attrs}]" if attrs else ""
        print(f"{indent}{agent.name} ({agent.kind}){suffix}")
    print()

    print("Opening stocks")
    print("-" * 62)
    for resource in region.resources:
        holder = region.agent(resource.custodian_id).name
        print(f"  {resource.specification_id:22} {resource.quantity:~P}  held by {holder}")
    print()

    print("Declared need, per community, per standard")
    print("-" * 62)
    communities = [a for a in region.agents if a.kind == "commune"]
    for agent in sorted(communities, key=lambda a: a.id):
        print(f"  {agent.name} (population {agent.attribute('population'):,.0f})")
        for standard in region.standards:
            need = standard.evaluate(agent).to("kcal/day")
            print(f"      {standard.id:42} {need.magnitude:>14,.0f} kcal/day")
            print(f"      {'':42} source: {standard.citation.source}")
    print()

    _print_phosphorus_budget(region)


def _print_phosphorus_budget(region: Region) -> None:
    """Show the constraint the reference question turns on.

    Nothing here chooses an allocation. It states what is available and what
    each option would consume, which is the whole of what the software is for
    (D-001).
    """
    stock = next(r for r in region.resources if r.specification_id == "soil.phosphorus")
    arable = sum(
        agent.attribute("land.arable_ha")
        for agent in region.agents
        if agent.has_attribute("land.arable_ha")
    )

    print("Phosphorus budget")
    print("-" * 62)
    print(f"  available            {stock.quantity:~P}")
    print(f"  arable land          {arable:,.0f} ha")
    print()
    print("  Demand if the whole valley were sown to one crop:")

    for recipe in sorted(region.recipes, key=lambda r: r.id):
        p_inputs = [
            f
            for f in recipe.inputs
            if f.specification_id == "soil.phosphorus" and f.action is Action.CONSUME
        ]
        if not p_inputs:
            continue
        per_ha = p_inputs[0].quantity.to("kgP").magnitude
        total = per_ha * arable
        ratio = total / stock.quantity.to("kgP").magnitude
        verdict = "sufficient" if ratio <= 1.0 else f"{ratio:.1f}x available"
        print(f"    {recipe.name:36} {per_ha:5.1f} kgP/ha  ->  {total:9,.0f} kgP  ({verdict})")

    print()
    print("  The valley cannot sow everything it could otherwise sow. Which")
    print("  crops get the phosphorus is a decision for the people of the")
    print("  valley; PDC's job is to make the consequences of each option")
    print("  legible before they choose, and to record what they chose.")


def _print_coefficients() -> None:
    print("Coefficient table")
    print("=" * 62)
    illustrative = 0
    for coefficient in coefficients_module.ALL:
        marker = "!" if coefficient.is_illustrative else " "
        illustrative += coefficient.is_illustrative
        print(f" {marker} {coefficient.name:34} {coefficient.value:~P}")
        print(f"     {coefficient.citation}")
    print()
    total = len(coefficients_module.ALL)
    print(f"{illustrative} of {total} are illustrative (marked !) and are refused")
    print("by Coefficient.check_usable(). Replacing them with sourced figures")
    print("is the most useful contribution to this project — see CONTRIBUTING.md.")


def _print_standards(region: Region) -> None:
    payload = [
        {
            "id": standard.id,
            "name": standard.name,
            "author": standard.author_id,
            "version": standard.version,
            "citation": str(standard.citation),
            "produces": standard.produces_specification_id,
            "requires": list(standard.requires),
            "expression": to_json(standard.expression),
        }
        for standard in region.standards
    ]
    print(json.dumps(payload, indent=2))


def _print_cost(region: Region, specification: str, quantity: float, unit: str) -> None:
    """Show what a resource cost, as physically distinct quantities.

    There is no total line, and there will not be one. Summing kilograms of
    phosphorus with labour-hours needs an exchange rate between them, and
    choosing one is a political act rather than an arithmetic one (D-002).
    """
    result = rollup(specification, Q(quantity, unit), region.recipes)

    print(f"Cost of {result.quantity:~P} of {result.specification_id}")
    print("=" * 62)
    for component, value in result.cost:
        print(f"  {component:22} {value:~P}")
    print()

    if result.cost.attributions:
        print("  Under attribution rules:")
        for record in result.cost.attributions:
            print(f"    {record.process_id}: {record.rule_name}")
        print()

    print("  No total. These are physically distinct quantities and adding")
    print("  them would require an exchange rate between phosphorus and")
    print("  labour — which is a decision for people, not arithmetic.")


SCENARIOS = ("grain-first", "split")


def _scenario_for(name: str, periods: int):  # type: ignore[no-untyped-def]
    return grain_first_scenario(periods) if name == "grain-first" else split_scenario(periods)


def _run(region: Region, name: str, periods: int) -> ForwardRun:
    scenario = _scenario_for(name, periods)
    return run_forward(
        scenario,
        agents=region.agents,
        recipes=region.recipes,
        standards=region.standards,
        compositions=region.compositions,
        opening=opening_state(),
    )


def _print_comparison(region: Region, periods: int) -> None:
    """Two allocations, side by side, per community.

    There is no verdict line and there will not be one. The point of showing
    both is that choosing between them is not a calculation (D-001).
    """
    runs = [_run(region, name, periods) for name in SCENARIOS]
    communes = sorted((a for a in region.agents if a.kind == "commune"), key=lambda a: a.id)

    print(f"Two allocations of the same {11000:,} kg of phosphorus")
    print("=" * 74)
    for run in runs:
        print(f"  {run.scenario_label}")
        for assumption in run.assumptions:
            print(f"      assuming {assumption}")
    print()

    header = f"{'community':16}" + "".join(f"{run.scenario_label:>28}" for run in runs)
    print(header)
    print(f"{'':16}" + "".join(f"{'periods 0 / 1 / 2':>28}" for _ in runs))
    print("-" * 74)

    for agent in communes:
        row = f"{agent.name:16}"
        for run in runs:
            outcomes = run.needs_for(agent.id, CONSUMPTION_STANDARD)
            shares = [
                100.0 * o.available.to("kcal").magnitude / o.required.to("kcal").magnitude
                for o in outcomes
            ]
            row += "".join(f"{share:9.1f}%" for share in shares).rjust(28)
        print(row)

    print()
    print("  Percentages are of each community's own declared adequate standard.")
    print("  They are not added together, and there is no valley-wide score:")
    print("  one allocation can be better in aggregate while leaving a")
    print("  community with nothing, and a single number would hide that.")


def _print_explanation(region: Region, agent_id: str, scenario: str, period: int) -> None:
    run = _run(region, scenario, max(period + 1, 3))
    outcomes = [
        o
        for o in run.period(period).needs
        if o.agent_id == agent_id and o.standard_id == CONSUMPTION_STANDARD
    ]
    if not outcomes:
        raise SystemExit(f"no outcome for {agent_id!r} in period {period}")

    print(f"Why: {agent_id}, period {period}, under {run.scenario_label}")
    print("=" * 74)
    print(render_text(outcomes[0].cause))


def _write_export(region: Region, path: pathlib.Path, name: str, periods: int) -> None:
    """Write the artefact people argue over.

    Self-contained: the question, the assumptions, the coefficient digests,
    and the answer. Someone else runs `pdc verify` on it against their own
    mirror and finds out whether they disagree, and about what.
    """
    scenario = _scenario_for(name, periods)
    run = _run(region, name, periods)
    branch = Branch(
        label=scenario.label,
        assumptions=(
            Assumption(
                kind=AssumptionKind.SET_CONSUMPTION_STANDARD,
                target=("scenario",),
                value=scenario.consumption_standard_id,
                rationale="the standard the valley agreed describes ordinary life",
            ),
        ),
    )
    document = build_export(
        run,
        scenario,
        recipes=region.recipes,
        standards=region.standards,
        branch=branch,
    )
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")

    print(f"wrote {path}")
    print(f"  scenario        {scenario.label}")
    print(f"  branch          {short(document['branch_digest'])}")
    print(f"  recipes         {short(document['recipes_digest'])}")
    print(f"  standards       {short(document['standards_digest'])}")
    print(f"  results         {short(document['results_digest'])}")
    print()
    print("  Hand this to anyone with a copy of the model. `pdc verify` tells")
    print("  them whether they get the same answer, and if not, whether it is")
    print("  because they believe different coefficients.")


def _verify_export(region: Region, path: pathlib.Path) -> int:
    document = json.loads(path.read_text())
    label = document["scenario"]["label"]
    name = "grain-first" if label.startswith("grain") else "split"
    run = _run(region, name, document["scenario"]["periods"])

    result = verify(document, run, recipes=region.recipes, standards=region.standards)

    print(f"Verifying {path}")
    print("=" * 74)
    print(f"  recipes    {'match' if result.recipes_match else 'DIFFER'}")
    print(f"  standards  {'match' if result.standards_match else 'DIFFER'}")
    print(f"  results    {'match' if result.results_match else 'DIFFER'}")
    print()
    print(f"  {result.summary()}")
    if result.notes:
        print()
        for note in result.notes:
            print(f"    {note}")
    return 0 if result.reproduced else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pdc",
        description=(
            "Production and Distribution Coordination. Computes the state of a "
            "resource system and the consequences of proposed changes. It does "
            "not choose between them."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("region", help="describe the synthetic reference region")
    subparsers.add_parser("coefficients", help="list the coefficient table with provenance")
    subparsers.add_parser(
        "standards", help="emit need standards as canonical JSON, for independent evaluation"
    )
    cost_parser = subparsers.add_parser(
        "cost", help="roll a resource back to the primary inputs that produced it"
    )
    cost_parser.add_argument("specification", help="resource specification id, e.g. bread")
    cost_parser.add_argument("--quantity", type=float, default=1.0)
    cost_parser.add_argument("--unit", default="tFW")
    compare_parser = subparsers.add_parser(
        "compare", help="run the reference allocations forward and show both outcomes"
    )
    compare_parser.add_argument("--periods", type=int, default=3)
    explain_parser = subparsers.add_parser(
        "explain", help="show the chain of consequence behind one community's shortfall"
    )
    explain_parser.add_argument("agent", help="community id, e.g. chakar")
    explain_parser.add_argument("--scenario", default="grain-first", choices=SCENARIOS)
    explain_parser.add_argument("--period", type=int, default=1)
    export_parser = subparsers.add_parser(
        "export", help="write a self-contained, reproducible scenario document"
    )
    export_parser.add_argument("path", type=pathlib.Path)
    export_parser.add_argument("--scenario", default="grain-first", choices=SCENARIOS)
    export_parser.add_argument("--periods", type=int, default=3)
    verify_parser = subparsers.add_parser(
        "verify", help="re-run someone else's export and report where you disagree"
    )
    verify_parser.add_argument("path", type=pathlib.Path)

    args = parser.parse_args(argv)
    region = build_reference_region()

    if args.command == "region":
        _print_region(region)
    elif args.command == "coefficients":
        _print_coefficients()
    elif args.command == "standards":
        _print_standards(region)
    elif args.command == "cost":
        _print_cost(region, args.specification, args.quantity, args.unit)
    elif args.command == "compare":
        _print_comparison(region, args.periods)
    elif args.command == "explain":
        _print_explanation(region, args.agent, args.scenario, args.period)
    elif args.command == "export":
        _write_export(region, args.path, args.scenario, args.periods)
    elif args.command == "verify":
        return _verify_export(region, args.path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
