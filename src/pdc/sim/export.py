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

EXPORT_FORMAT = 2
"""Format 2 carries the coefficients themselves, not only their digest.

Format 1 could report *that* two models disagreed. Answering "which variable
are they tweaking?" — the question the whole audit right exists to serve —
needs the numbers, so they travel with the document. Format 1 exports are
still readable; they just cannot be diffed field by field.
"""


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


def recipes_payload(recipes: Sequence[RecipeProcess]) -> list[dict[str, Any]]:
    """The coefficients, in full, with their citations.

    Travelling with the export so that a disagreement can be located rather
    than merely detected.
    """
    return [
        {
            "id": recipe.id,
            "name": recipe.name,
            "process_specification": recipe.process_specification_id,
            "duration_periods": recipe.duration_periods,
            "flows": [
                {
                    "action": flow.action.value,
                    "specification": flow.specification_id,
                    "quantity": quantity_json(flow.quantity),
                    "lag": flow.lag_periods,
                    "citation": {
                        "source": flow.citation.source,
                        "provenance": flow.citation.provenance.value,
                        "locator": flow.citation.locator,
                    },
                }
                for flow in recipe.flows()
            ],
        }
        for recipe in sorted(recipes, key=lambda r: r.id)
    ]


def standards_payload(standards: Sequence[NeedStandard]) -> list[dict[str, Any]]:
    return [
        {
            "id": standard.id,
            "name": standard.name,
            "version": standard.version,
            "author": standard.author_id,
            "expression": to_json(standard.expression),
            "citation": {
                "source": standard.citation.source,
                "provenance": standard.citation.provenance.value,
            },
        }
        for standard in sorted(standards, key=lambda s: s.id)
    ]


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
        "recipes": recipes_payload(recipes),
        "standards": standards_payload(standards),
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


@dataclass(frozen=True, slots=True)
class CoefficientDifference:
    """One number two models disagree about.

    The unit of the conversation this project exists to enable: not "your
    answer is wrong" but "you think a hectare of alfalfa takes 22.5 kg of
    phosphorus and I think it takes 15, and here is where each of us got that".
    """

    recipe_id: str
    recipe_name: str
    action: str
    specification_id: str
    theirs: dict[str, Any] | None
    mine: dict[str, Any] | None
    their_citation: str | None = None
    my_citation: str | None = None

    @property
    def kind(self) -> str:
        if self.theirs is None:
            return "only in mine"
        if self.mine is None:
            return "only in theirs"
        return "differs"

    @property
    def ratio(self) -> float | None:
        """How many times larger their figure is than mine.

        None when the two are not comparable — different units, or one side
        absent — because a ratio across units would be exactly the reduction
        this project refuses.
        """
        if self.theirs is None or self.mine is None:
            return None
        if self.theirs["units"] != self.mine["units"]:
            return None
        if not self.mine["magnitude"]:
            return None
        return self.theirs["magnitude"] / self.mine["magnitude"]


def diff_recipes(
    export: dict[str, Any], recipes: Sequence[RecipeProcess]
) -> tuple[CoefficientDifference, ...]:
    """Locate every coefficient two models disagree about.

    This is the "why does this farm claim ten times the labour of any
    comparable farm" workflow, answered mechanically. Signatures would tell
    you who asserted a figure; this tells you whether the figure is plausible,
    which is the question people actually ask (D-010).
    """
    theirs = {entry["id"]: entry for entry in export.get("recipes", [])}
    mine = {entry["id"]: entry for entry in recipes_payload(recipes)}

    differences: list[CoefficientDifference] = []

    for recipe_id in sorted(set(theirs) | set(mine)):
        their_recipe = theirs.get(recipe_id)
        my_recipe = mine.get(recipe_id)
        name = (their_recipe or my_recipe or {}).get("name", recipe_id)

        their_flows = {
            (f["action"], f["specification"]): f for f in (their_recipe or {}).get("flows", [])
        }
        my_flows = {
            (f["action"], f["specification"]): f for f in (my_recipe or {}).get("flows", [])
        }

        for key in sorted(set(their_flows) | set(my_flows)):
            their_flow = their_flows.get(key)
            my_flow = my_flows.get(key)

            if their_flow and my_flow and their_flow["quantity"] == my_flow["quantity"]:
                continue

            differences.append(
                CoefficientDifference(
                    recipe_id=recipe_id,
                    recipe_name=name,
                    action=key[0],
                    specification_id=key[1],
                    theirs=their_flow["quantity"] if their_flow else None,
                    mine=my_flow["quantity"] if my_flow else None,
                    their_citation=(their_flow or {}).get("citation", {}).get("source"),
                    my_citation=(my_flow or {}).get("citation", {}).get("source"),
                )
            )

    return tuple(differences)


def is_diffable(export: dict[str, Any]) -> bool:
    """Whether an export carries coefficients rather than only their digest."""
    return bool(export.get("recipes"))
