"""Command-line shell.

A shell, not the kernel. Nothing under ``pdc.units``, ``pdc.ontology``,
``pdc.needs``, or ``pdc.seed`` may import from here.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from pdc.needs import to_json
from pdc.ontology import Action
from pdc.seed import Region, build_reference_region
from pdc.seed import coefficients as coefficients_module


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

    args = parser.parse_args(argv)
    region = build_reference_region()

    if args.command == "region":
        _print_region(region)
    elif args.command == "coefficients":
        _print_coefficients()
    elif args.command == "standards":
        _print_standards(region)

    return 0


if __name__ == "__main__":
    sys.exit(main())
