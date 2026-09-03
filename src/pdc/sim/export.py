"""Scenario export and independent verification.

The artefact people argue over. An export is self-contained: the question
asked, the assumptions behind it, the coefficients it relied on, and the
answer it produced. Hand someone the file and they can re-run it against their
own mirror.

Two things they can then find out, which are different questions:

- **Did I get the same answer from the same inputs?** If not, one of the two
  implementations is broken, and the digests say which part differs.
- **Do I get a different answer because I believe different coefficients?**
  That is not a bug. That is the disagreement the project exists to surface,
  and it should be legible rather than buried.

No file I/O here: the kernel does not touch the filesystem (D-005). This
module produces and consumes plain dictionaries; the CLI reads and writes.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pdc import __version__
from pdc.needs import NeedStandard, to_json
from pdc.ontology import RecipeProcess
from pdc.sim.branch import Branch
from pdc.sim.forward import ForwardRun
from pdc.sim.identity import digest, quantity_json
from pdc.sim.world import Scenario

EXPORT_FORMAT = 1


def recipes_digest(recipes: Sequence[RecipeProcess]) -> str:
    """Content address over the coefficients that drive production.

    The number two people most often disagree about, so it gets its own digest
    rather than being folded into a single opaque region hash: a mismatch here
    says "we believe different things about farming", which is a different
    conversation from "our code differs".
    """
    return digest(
        [
            {
                "recipe": recipe.id,
                "flows": [
                    {
                        "action": flow.action.value,
                        "specification": flow.specification_id,
                        "quantity": quantity_json(flow.quantity),
                        "lag": flow.lag_periods,
                        "citation": flow.citation.source,
                    }
                    for flow in recipe.flows()
                ],
            }
            for recipe in sorted(recipes, key=lambda r: r.id)
        ]
    )


def standards_digest(standards: Sequence[NeedStandard]) -> str:
    """Content address over what the model believes people require."""
    return digest(
        [
            {
                "id": standard.id,
                "version": standard.version,
                "expression": to_json(standard.expression),
                "citation": standard.citation.source,
            }
            for standard in sorted(standards, key=lambda s: s.id)
        ]
    )


def scenario_json(scenario: Scenario) -> dict[str, Any]:
    return {
        "label": scenario.label,
        "periods": scenario.periods,
        "consumption_standard": scenario.consumption_standard_id,
        "allocation": {
            "label": scenario.allocation.label,
            "shares": [
                {"agent": agent, "specification": spec, "quantity": quantity_json(q)}
                for (agent, spec), q in scenario.allocation.shares
            ],
        },
        "plans": [
            {
                "agent": plan.agent_id,
                "recipe": plan.recipe_id,
                "batches": plan.intended_batches,
                "from": plan.from_period,
                "through": plan.through_period,
            }
            for plan in sorted(scenario.plans, key=lambda p: (p.agent_id, p.recipe_id))
        ],
    }


def results_json(run: ForwardRun) -> dict[str, Any]:
    """The answer, in a form a renderer can display and a checker can compare.

    Includes the explanation trees, because "what happened" without "why" is
    not something anyone can argue with.
    """
    return {
        "scenario": run.scenario_label,
        "assumptions": list(run.assumptions),
        "periods": [
            {
                "period": result.period,
                "processes": [
                    {
                        "agent": outcome.agent_id,
                        "recipe": outcome.recipe_id,
                        "intended": outcome.intended_batches,
                        "achieved": outcome.achieved_batches,
                        "binding": outcome.binding_specification_id,
                    }
                    for outcome in sorted(result.processes, key=lambda o: (o.agent_id, o.recipe_id))
                ],
                "needs": [
                    {
                        "agent": outcome.agent_id,
                        "standard": outcome.standard_id,
                        "required": quantity_json(outcome.required),
                        "available": quantity_json(outcome.available),
                        "met": outcome.met,
                        "explanation": outcome.cause.to_json(),
                    }
                    for outcome in sorted(result.needs, key=lambda o: (o.agent_id, o.standard_id))
                ],
            }
            for result in run.periods
        ],
    }


def build_export(
    run: ForwardRun,
    scenario: Scenario,
    *,
    recipes: Sequence[RecipeProcess],
    standards: Sequence[NeedStandard],
    branch: Branch | None = None,
) -> dict[str, Any]:
    """Bundle a run into a self-contained, reproducible document."""
    results = results_json(run)
    return {
        "format": EXPORT_FORMAT,
        "kernel_version": __version__,
        "recipes_digest": recipes_digest(recipes),
        "standards_digest": standards_digest(standards),
        "branch": branch.to_json() if branch else None,
        "branch_digest": branch.digest if branch else None,
        "scenario": scenario_json(scenario),
        "results": results,
        "results_digest": digest(results),
    }


@dataclass(frozen=True, slots=True)
class Verification:
    """The outcome of re-running someone else's export.

    Deliberately not a boolean. "Your answer differs from mine" and "your
    answer differs because you believe different coefficients" are different
    findings, and collapsing them would hide the interesting one.
    """

    results_match: bool
    recipes_match: bool
    standards_match: bool
    kernel_matches: bool
    notes: tuple[str, ...] = ()

    @property
    def reproduced(self) -> bool:
        """True when the same inputs gave the same answer."""
        return self.results_match

    def summary(self) -> str:
        if self.results_match and self.recipes_match and self.standards_match:
            return "reproduced exactly: same coefficients, same answer"
        if self.results_match:
            return "same answer, but the inputs differ — check the digests"
        if not self.recipes_match:
            return (
                "different answer, and the recipe coefficients differ. This is a "
                "disagreement about the world, not a bug: compare the coefficients "
                "and their citations."
            )
        return (
            "different answer from the same coefficients. One of the two implementations is wrong."
        )


def verify(
    export: dict[str, Any],
    run: ForwardRun,
    *,
    recipes: Sequence[RecipeProcess],
    standards: Sequence[NeedStandard],
) -> Verification:
    """Compare an export against a locally computed run."""
    local = results_json(run)
    notes: list[str] = []

    recipes_match = export.get("recipes_digest") == recipes_digest(recipes)
    standards_match = export.get("standards_digest") == standards_digest(standards)
    results_match = export.get("results_digest") == digest(local)
    kernel_matches = export.get("kernel_version") == __version__

    if not kernel_matches:
        notes.append(
            f"kernel version differs: export {export.get('kernel_version')}, local {__version__}"
        )
    if not recipes_match:
        notes.append("recipe coefficients differ — the models disagree about production")
    if not standards_match:
        notes.append("need standards differ — the models disagree about requirement")

    if not results_match:
        notes.extend(_first_divergences(export.get("results", {}), local))

    return Verification(
        results_match=results_match,
        recipes_match=recipes_match,
        standards_match=standards_match,
        kernel_matches=kernel_matches,
        notes=tuple(notes),
    )


def _first_divergences(
    theirs: dict[str, Any],
    mine: dict[str, Any],
    per_period: int = 3,
    total: int = 9,
) -> list[str]:
    """Locate where two result sets differ.

    Reporting "they differ" is nearly useless; reporting which community, in
    which period, by how much, is the thing that starts a conversation.

    Divergences are capped per period as well as overall, because the
    interesting difference is often not in the first year. Two allocations
    frequently agree at the start and separate later — that separation is the
    whole point of running forward — and a flat cap would spend its budget on
    period zero and never show it.
    """
    notes: list[str] = []
    their_periods = {p["period"]: p for p in theirs.get("periods", [])}

    for period in mine.get("periods", []):
        if len(notes) >= total:
            break

        counterpart = their_periods.get(period["period"])
        if counterpart is None:
            notes.append(f"period {period['period']} missing from the export")
            continue

        their_needs = {(n["agent"], n["standard"]): n for n in counterpart["needs"]}
        found = 0
        for need in period["needs"]:
            if found >= per_period or len(notes) >= total:
                break
            key = (need["agent"], need["standard"])
            other = their_needs.get(key)
            if other is None:
                notes.append(f"period {period['period']}: {key[0]} missing from the export")
                found += 1
            elif other["available"] != need["available"]:
                notes.append(
                    f"period {period['period']}, {key[0]}, {key[1]}: "
                    f"export has {other['available']['magnitude']:,.0f} "
                    f"{other['available']['units']}, local has "
                    f"{need['available']['magnitude']:,.0f} {need['available']['units']}"
                )
                found += 1

    return notes
