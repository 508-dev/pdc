"""Export, share, reopen.

The loop the project is for: someone runs a scenario, hands you the file, and
you open the same question against *your* model. Not their answer rendered
back at you — your answer to their question, and a list of the numbers you
would each change.
"""

from __future__ import annotations

import json
from urllib.parse import parse_qsl

import pytest

django = pytest.importorskip("django", reason="the web extra is not installed")

from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402
from django.test import Client  # noqa: E402

from pdc.seed import build_reference_region  # noqa: E402
from pdc.seed.scenarios import (  # noqa: E402
    CONSUMPTION_STANDARD,
    grain_first_scenario,
    opening_state,
    scenario_from_branch,
)
from pdc.sim import (  # noqa: E402
    Assumption,
    AssumptionKind,
    Branch,
    build_export,
    results_core,
    run_forward,
)
from pdc.web.params import ExploreParams, params_from_branch  # noqa: E402

STANDARDS = {CONSUMPTION_STANDARD, "sphere-2018:food-energy"}


@pytest.fixture
def client() -> Client:
    return Client()


# --------------------------------------------------------------------------
# Recovering a scenario from its branch
# --------------------------------------------------------------------------


@pytest.mark.parametrize("percent", ["0", "25", "40", "100"])
def test_controls_round_trip_through_a_branch(percent: str) -> None:
    params = ExploreParams.parse({"alfalfa": percent, "periods": "4"}, STANDARDS)
    assert params_from_branch(params.to_branch(), STANDARDS) == params


def test_a_branch_the_controls_cannot_express_is_declined() -> None:
    """Showing an approximation of someone's scenario and labelling it theirs
    would be a small lie of exactly the kind this project exists to make
    impossible."""
    branch = Branch(
        "removes-a-herd",
        (Assumption(AssumptionKind.REMOVE_PLAN, ("ranch-c", "recipe.dairy")),),
    )
    assert params_from_branch(branch, STANDARDS) is None


def test_a_hand_altered_share_is_declined() -> None:
    """The dial only claims a branch when regenerating from it reproduces
    every share exactly."""
    from pdc.units import Q

    params = ExploreParams.parse({"alfalfa": "40"}, STANDARDS)
    branch = params.to_branch()
    tampered = Branch(
        branch.label,
        tuple(
            Assumption(a.kind, a.target, Q(999.0, "kgP"), a.rationale)
            if a.kind is AssumptionKind.SET_ALLOCATION_SHARE and a.target[0] == "farm-b"
            else a
            for a in branch.assumptions
        ),
    )
    assert params_from_branch(tampered, STANDARDS) is None


# --------------------------------------------------------------------------
# Verification is about numbers, not names
# --------------------------------------------------------------------------


def test_results_digest_ignores_labels_and_prose() -> None:
    """Two people who ran the same question and got the same numbers agree,
    even if one called it "grain-first" and the other "what Sadik proposed"."""
    import dataclasses

    region = build_reference_region()
    forward = run_forward(
        grain_first_scenario(),
        agents=region.agents,
        recipes=region.recipes,
        standards=region.standards,
        compositions=region.compositions,
        opening=opening_state(),
    )
    renamed = dataclasses.replace(
        forward, scenario_label="what Sadik proposed", assumptions=("differently worded",)
    )
    assert results_core(forward) == results_core(renamed)


# --------------------------------------------------------------------------
# The whole loop, through the interface
# --------------------------------------------------------------------------


def _download(client: Client, query: str) -> bytes:
    response = client.get(f"/explore/export/?{query}")
    assert response.status_code == 200
    return bytes(response.content)


def test_the_explorer_exports_what_is_on_screen(client: Client) -> None:
    params = ExploreParams.parse({"alfalfa": "40"}, STANDARDS)
    document = json.loads(_download(client, params.to_query()))

    assert document["branch_digest"] == params.to_branch().digest
    assert document["recipes"], "the coefficients must travel with the answer"
    assert document["results"]["periods"]


def test_the_download_is_offered_as_a_file(client: Client) -> None:
    response = client.get("/explore/export/?alfalfa=40")
    assert response["Content-Type"] == "application/json"
    assert "attachment" in response["Content-Disposition"]
    assert ".json" in response["Content-Disposition"]


def test_a_bad_parameter_does_not_produce_a_misleading_file(client: Client) -> None:
    assert client.get("/explore/export/?alfalfa=900").status_code == 400


def test_exported_then_uploaded_reproduces_exactly(client: Client) -> None:
    """The loop closing on itself: our own scenario, round-tripped, agrees."""
    payload = _download(client, "alfalfa=40&periods=3")
    response = client.post(
        "/compare-models/", {"export": SimpleUploadedFile("theirs.json", payload)}
    )
    body = " ".join(response.content.decode().split())

    assert "reproduced exactly" in body
    assert "Every coefficient matches" in body


def test_an_uploaded_scenario_can_be_reopened_against_our_model(client: Client) -> None:
    """The move that matters: the same question, asked of a different model."""
    payload = _download(client, "alfalfa=65&periods=4")
    body = client.post(
        "/compare-models/", {"export": SimpleUploadedFile("theirs.json", payload)}
    ).content.decode()

    assert "Open their scenario against" in body

    import re

    match = re.search(r'href="(/explore/\?[^"]+)"', body)
    assert match is not None
    link = match.group(1).replace("&amp;", "&")

    recovered = ExploreParams.parse(dict(parse_qsl(link.split("?", 1)[1])), STANDARDS)
    assert recovered.alfalfa_percent == pytest.approx(65.0)
    assert recovered.periods == 4
    assert client.get(link).status_code == 200


def test_verification_uses_their_assumptions_not_a_guessed_preset(client: Client) -> None:
    """Guessing from a label would verify our answer to a slightly different
    question, which is a worse failure than admitting we cannot read it."""
    payload = _download(client, "alfalfa=65&periods=4")
    body = client.post(
        "/compare-models/", {"export": SimpleUploadedFile("theirs.json", payload)}
    ).content.decode()
    assert "their own assumptions" in body


def test_a_branch_the_controls_cannot_express_still_verifies(client: Client) -> None:
    """Rebuilding a scenario and reopening it are different problems.

    Any branch can be applied exactly, so verification always uses their own
    assumptions. Only the explorer's controls can fail to represent one, and
    then the page declines to reopen it rather than showing an approximation.
    """
    region = build_reference_region()
    branch = Branch(
        "no-dairy-at-chakar",
        (Assumption(AssumptionKind.REMOVE_PLAN, ("ranch-c", "recipe.dairy")),),
    )
    scenario = scenario_from_branch(branch, 3)
    forward = run_forward(
        scenario,
        agents=region.agents,
        recipes=region.recipes,
        standards=region.standards,
        compositions=region.compositions,
        opening=opening_state(),
    )
    payload = json.dumps(
        build_export(
            forward, scenario, recipes=region.recipes, standards=region.standards, branch=branch
        )
    ).encode()

    body = " ".join(
        client.post("/compare-models/", {"export": SimpleUploadedFile("t.json", payload)})
        .content.decode()
        .split()
    )

    assert "their own assumptions" in body
    assert "reproduced exactly" in body
    assert "cannot be opened in the explorer" in body


def test_an_export_with_no_branch_says_it_fell_back_to_a_preset(client: Client) -> None:
    region = build_reference_region()
    forward = run_forward(
        grain_first_scenario(),
        agents=region.agents,
        recipes=region.recipes,
        standards=region.standards,
        compositions=region.compositions,
        opening=opening_state(),
    )
    payload = json.dumps(
        build_export(
            forward, grain_first_scenario(), recipes=region.recipes, standards=region.standards
        )
    ).encode()

    body = " ".join(
        client.post("/compare-models/", {"export": SimpleUploadedFile("t.json", payload)})
        .content.decode()
        .split()
    )
    assert "carries no branch" in body
