"""The explorer.

Two things these tests are for. The obvious one is that the pages render. The
load-bearing one is that the interface agrees with the kernel: every figure on
screen must come from the same computation the command line uses, because a
screen that quietly disagrees with the model is a corruption vector under
D-010 and a subtle one, since both look right in isolation.
"""

from __future__ import annotations

import pytest

django = pytest.importorskip("django", reason="the web extra is not installed")

from django.test import Client  # noqa: E402

from pdc.seed.scenarios import CONSUMPTION_STANDARD  # noqa: E402
from pdc.web.context import readings, run  # noqa: E402


@pytest.fixture
def client() -> Client:
    return Client()


def test_overview_renders(client: Client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "Abbenay Valley" in body
    assert "Northsetting" in body


def test_overview_shows_standards_as_peers(client: Client) -> None:
    """D-006: no ladder. The page must not present one as the requirement."""
    body = client.get("/").content.decode()
    assert "Sphere" in body
    assert "peers, not a ladder" in body


def test_overview_shows_the_phosphorus_constraint(client: Client) -> None:
    body = client.get("/").content.decode()
    assert "11,000 kg" in body or "11000 kg" in body
    assert "will not say what" in body


def test_compare_renders_both_allocations(client: Client) -> None:
    response = client.get("/compare/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "grain-first" in body
    assert "split" in body


def test_compare_has_no_aggregate_row(client: Client) -> None:
    """The commitment that makes the whole comparison honest (D-002).

    An aggregate would report grain-first as the better option and hide that
    it takes Chakar to zero.
    """
    body = client.get("/compare/").content.decode()
    assert "no total row" in body
    for forbidden in ("Valley total", "Total:", "Overall score", "Aggregate:"):
        assert forbidden not in body


def test_compare_agrees_with_the_kernel(client: Client) -> None:
    """The interface formats; it does not compute."""
    body = client.get("/compare/").content.decode()
    rows = readings("grain-first", CONSUMPTION_STANDARD)
    for reading in rows["chakar"]:
        assert f"{reading.percentage:.1f}%" in body


def test_chakar_is_shown_as_destitute_under_grain_first(client: Client) -> None:
    body = client.get("/compare/").content.decode()
    assert "0.0%" in body
    assert 'class="num zero"' in body


def test_explain_shows_the_chain_to_a_cited_coefficient(client: Client) -> None:
    response = client.get("/explain/grain-first/chakar/1/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "limiting factor" in body
    assert "source:" in body
    assert "recipe.alfalfa requires soil.phosphorus" in body


def test_explain_marks_illustrative_coefficients(client: Client) -> None:
    """A reader must be able to see that a number is not sourced."""
    body = client.get("/explain/grain-first/chakar/1/").content.decode()
    assert "illustrative" in body


def test_explain_needs_no_javascript(client: Client) -> None:
    """Auditing the model must not require a working script engine.

    The causal chain uses <details>, which every browser expands unaided.
    """
    body = client.get("/explain/grain-first/chakar/1/").content.decode()
    assert "<details" in body
    assert "<script" not in body


def test_no_page_requires_javascript(client: Client) -> None:
    for url in ("/", "/compare/", "/explain/grain-first/chakar/1/"):
        assert "<script" not in client.get(url).content.decode()


def test_unknown_scenario_is_a_404(client: Client) -> None:
    assert client.get("/explain/no-such-scenario/chakar/1/").status_code == 404


def test_unknown_agent_is_a_404(client: Client) -> None:
    assert client.get("/explain/grain-first/atlantis/1/").status_code == 404


def test_period_past_the_end_is_a_404(client: Client) -> None:
    assert client.get("/explain/grain-first/chakar/99/").status_code == 404


def test_unknown_standard_is_a_404(client: Client) -> None:
    assert client.get("/?standard=made-up").status_code == 404


def test_the_explorer_has_no_database(client: Client) -> None:
    """No persistence, no users, nothing to protect. Every scenario the
    explorer can show is encoded in its URL."""
    from django.conf import settings

    # Django substitutes a dummy backend for an empty DATABASES, which raises
    # on any query. That is the behaviour wanted: an accidental model import
    # fails loudly rather than silently creating state.
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.dummy"
    assert settings.INSTALLED_APPS == []
    assert not any("auth" in m or "session" in m for m in settings.MIDDLEWARE)


def test_runs_are_cached_but_identical(client: Client) -> None:
    """Caching is safe precisely because the kernel is deterministic (D-005)."""
    assert run("grain-first") is run("grain-first")


# --------------------------------------------------------------------------
# Coefficient inspection and model comparison
# --------------------------------------------------------------------------


def test_coefficients_page_lists_every_number_with_its_source(client: Client) -> None:
    body = client.get("/coefficients/").content.decode()
    assert "soil.phosphorus" in body
    assert "illustrative" in body
    assert "Sphere" in body


def test_coefficients_page_says_how_many_are_unsourced(client: Client) -> None:
    """A reader must be able to tell how much of the model is a demonstration."""
    body = " ".join(client.get("/coefficients/").content.decode().split())
    assert "are illustrative" in body
    assert "needs no programming" in body


def test_compare_models_page_renders(client: Client) -> None:
    assert client.get("/compare-models/").status_code == 200


def test_uploading_our_own_export_finds_no_disagreement(client: Client, tmp_path) -> None:  # type: ignore[no-untyped-def]
    import json

    from pdc.seed import build_reference_region
    from pdc.seed.scenarios import grain_first_scenario
    from pdc.sim import build_export
    from pdc.web.context import run

    region = build_reference_region()
    document = build_export(
        run("grain-first"),
        grain_first_scenario(),
        recipes=region.recipes,
        standards=region.standards,
    )
    path = tmp_path / "ours.json"
    path.write_text(json.dumps(document))

    with path.open("rb") as handle:
        response = client.post("/compare-models/", {"export": handle})

    body = response.content.decode()
    assert response.status_code == 200
    assert "reproduced exactly" in body
    assert "Every coefficient matches" in body


def test_uploading_a_divergent_model_names_the_coefficient(client: Client, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Not "your answer is wrong", but "you think a hectare of alfalfa takes
    22.5 kg of phosphorus and I think it takes 15"."""
    import dataclasses
    import json

    from pdc.seed import build_reference_region
    from pdc.seed.scenarios import grain_first_scenario, opening_state
    from pdc.sim import build_export, run_forward
    from pdc.units import Q

    region = build_reference_region()
    theirs = tuple(
        dataclasses.replace(
            recipe,
            inputs=tuple(
                dataclasses.replace(flow, quantity=Q(15.0, "kgP"))
                if flow.specification_id == "soil.phosphorus"
                else flow
                for flow in recipe.inputs
            ),
        )
        if recipe.id == "recipe.alfalfa"
        else recipe
        for recipe in region.recipes
    )
    forward = run_forward(
        grain_first_scenario(),
        agents=region.agents,
        recipes=theirs,
        standards=region.standards,
        compositions=region.compositions,
        opening=opening_state(),
    )
    path = tmp_path / "theirs.json"
    path.write_text(
        json.dumps(
            build_export(
                forward, grain_first_scenario(), recipes=theirs, standards=region.standards
            )
        )
    )

    with path.open("rb") as handle:
        body = client.post("/compare-models/", {"export": handle}).content.decode()

    assert "Which numbers you disagree about" in body
    assert "soil.phosphorus" in body
    assert "22.50" in body and "15.00" in body
    assert "disagreement about the world" in " ".join(body.split())


def test_uploading_rubbish_is_rejected_gracefully(client: Client, tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "not-json.json"
    path.write_text("this is not JSON at all")
    with path.open("rb") as handle:
        response = client.post("/compare-models/", {"export": handle})
    assert response.status_code == 400
    assert b"does not parse" in response.content


def test_uploading_valid_json_that_is_not_an_export_is_rejected(client: Client, tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "other.json"
    path.write_text('{"hello": "world"}')
    with path.open("rb") as handle:
        response = client.post("/compare-models/", {"export": handle})
    assert response.status_code == 400
    assert b"not a PDC export" in response.content


def test_uploading_nothing_is_rejected(client: Client) -> None:
    response = client.post("/compare-models/", {})
    assert response.status_code == 400
