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
