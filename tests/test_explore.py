"""The explorer's controls.

The load-bearing property under test is that **every control maps to an
Assumption**. Anything the interface can express must also be a branch, a URL,
and an export — otherwise the audit right in D-010 applies only to scenarios
someone wrote in Python, and not to what people actually did on screen.
"""

from __future__ import annotations

import pytest

django = pytest.importorskip("django", reason="the web extra is not installed")

from django.test import Client  # noqa: E402

from pdc.seed.scenarios import CONSUMPTION_STANDARD  # noqa: E402
from pdc.sim import apply_branch  # noqa: E402
from pdc.web.context import readings_from_run, run_scenario  # noqa: E402
from pdc.web.params import NO_CONSUMPTION, ExploreParams, ParameterError  # noqa: E402

STANDARDS = {CONSUMPTION_STANDARD, "sphere-2018:food-energy"}


def text_of(response: object) -> str:
    """Rendered body with runs of whitespace collapsed.

    Templates wrap lines mid-sentence, so asserting on raw HTML makes tests
    fail for reflowing rather than for regressions.
    """
    return " ".join(response.content.decode().split())  # type: ignore[attr-defined]


@pytest.fixture
def client() -> Client:
    return Client()


def _params(**values: str) -> ExploreParams:
    return ExploreParams.parse(values, STANDARDS)


# --------------------------------------------------------------------------
# Controls are assumptions
# --------------------------------------------------------------------------


def test_every_control_becomes_an_assumption() -> None:
    branch = _params(alfalfa="40", periods="4", standard=CONSUMPTION_STANDARD).to_branch()
    kinds = {a.kind.value for a in branch.assumptions}
    assert "set_allocation_share" in kinds
    assert "set_periods" in kinds
    assert "set_consumption_standard" in kinds


def test_the_slider_records_per_farm_shares_not_the_dial_position() -> None:
    """One slider becomes several assumptions because that is what it does.

    Recording the dial position instead would hide that dividing within each
    group by area is itself a choice, and hidden choices are the thing this
    project exists to refuse.
    """
    branch = _params(alfalfa="40").to_branch()
    shares = [a for a in branch.assumptions if a.kind.value == "set_allocation_share"]
    assert len(shares) > 1
    assert {a.target[0] for a in shares} >= {"farm-a", "farm-b", "farm-f"}


def test_every_assumption_carries_a_rationale() -> None:
    """A branch is an argument, and an argument with unlabelled premises is
    hard to contest."""
    for assumption in _params(alfalfa="40").to_branch().assumptions:
        assert assumption.rationale


def test_the_scenario_is_the_branch_applied() -> None:
    """The branch is the single description of the view, so it cannot fall
    out of step with what is on screen."""
    params = _params(alfalfa="40", periods="3")
    scenario = params.to_scenario()
    granted = scenario.allocation.granted("farm-b", "soil.phosphorus")
    assert granted is not None
    assert granted.to("kgP").magnitude > 0


def test_identical_parameters_give_an_identical_branch_digest() -> None:
    assert _params(alfalfa="40").to_branch().digest == _params(alfalfa="40").to_branch().digest


def test_different_parameters_give_a_different_digest() -> None:
    assert _params(alfalfa="40").to_branch().digest != _params(alfalfa="60").to_branch().digest


# --------------------------------------------------------------------------
# The URL is the scenario
# --------------------------------------------------------------------------


def test_parameters_round_trip_through_the_query_string() -> None:
    from urllib.parse import parse_qsl

    original = _params(alfalfa="40", periods="5", standard="sphere-2018:food-energy")
    restored = ExploreParams.parse(dict(parse_qsl(original.to_query())), STANDARDS)
    assert restored == original


def test_no_consumption_round_trips() -> None:
    from urllib.parse import parse_qsl

    original = _params(standard=NO_CONSUMPTION)
    assert original.standard_id is None
    restored = ExploreParams.parse(dict(parse_qsl(original.to_query())), STANDARDS)
    assert restored == original


@pytest.mark.parametrize(
    "values",
    [
        {"alfalfa": "900"},
        {"alfalfa": "-5"},
        {"alfalfa": "lots"},
        {"periods": "0"},
        {"periods": "999"},
        {"periods": "some"},
        {"standard": "invented"},
    ],
)
def test_out_of_range_parameters_are_rejected_not_clamped(values: dict[str, str]) -> None:
    """Silently adjusting what was asked for would make a URL mean something
    other than it says, which for a tool about being checkable is the wrong
    trade."""
    with pytest.raises(ParameterError):
        ExploreParams.parse(values, STANDARDS)


def test_a_bad_parameter_is_a_400_not_a_silent_default(client: Client) -> None:
    response = client.get("/explore/?alfalfa=900")
    assert response.status_code == 400
    assert b"between 0 and 100" in response.content


# --------------------------------------------------------------------------
# The page
# --------------------------------------------------------------------------


def test_explore_renders(client: Client) -> None:
    response = client.get("/explore/")
    assert response.status_code == 200
    body = text_of(response)
    assert 'type="range"' in body
    assert "Nothing here is a recommendation" in body


def test_moving_the_dial_changes_the_outcome(client: Client) -> None:
    grain = client.get("/explore/?alfalfa=0").content.decode()
    forage = client.get("/explore/?alfalfa=40").content.decode()
    assert grain != forage


def test_the_dial_moves_chakar_off_zero() -> None:
    """The valley's actual argument, made continuous."""

    def chakar_at(percent: str) -> float:
        params = _params(alfalfa=percent)
        table = readings_from_run(run_scenario(params.to_scenario()), CONSUMPTION_STANDARD)
        return table["chakar"][-1].percentage

    assert chakar_at("0") == pytest.approx(0.0)
    assert chakar_at("40") > 0.0


def test_more_forage_eventually_helps_nobody() -> None:
    """Past the point the herd can eat, further forage buys Chakar nothing
    and costs everyone else. The dial should make that legible rather than
    implying the trade continues."""

    def at(percent: str, agent: str) -> float:
        params = _params(alfalfa=percent)
        table = readings_from_run(run_scenario(params.to_scenario()), CONSUMPTION_STANDARD)
        return table[agent][-1].percentage

    assert at("40", "chakar") == pytest.approx(at("100", "chakar"))
    assert at("100", "northsetting") < at("40", "northsetting")


def test_htmx_requests_get_a_fragment(client: Client) -> None:
    response = client.get("/explore/?alfalfa=40", headers={"HX-Request": "true"})
    assert response.status_code == 200
    body = response.content.decode()
    assert "<html" not in body
    assert "<table" in body


def test_the_fragment_and_the_full_page_agree(client: Client) -> None:
    """A link someone shares must show what the sharer saw.

    The page and the fragment render from one context for exactly this
    reason; this test is what keeps that true.
    """
    full = client.get("/explore/?alfalfa=40").content.decode()
    fragment = client.get("/explore/?alfalfa=40", headers={"HX-Request": "true"}).content.decode()
    table = fragment[fragment.index("<table") : fragment.index("</table>")]
    assert table in full


def test_the_form_works_without_javascript(client: Client) -> None:
    """Progressive enhancement: HTMX swaps the results when it can, and the
    plain GET form reloads the page when it cannot."""
    body = text_of(client.get("/explore/"))
    assert 'method="get"' in body
    assert 'type="submit"' in body
    assert "<noscript>" in body


def test_htmx_is_vendored_not_fetched_from_a_cdn(client: Client) -> None:
    """A tool a syndicate self-hosts should not depend on someone else's
    uptime, someone else's logs, or a working route to the wider internet."""
    body = text_of(client.get("/explore/"))
    assert "unpkg.com" not in body
    assert "cdn." not in body
    assert client.get("/htmx.js").status_code == 200


def test_the_view_shows_its_own_assumptions(client: Client) -> None:
    body = text_of(client.get("/explore/?alfalfa=40"))
    assert "This view, as assumptions" in body
    assert "set_allocation_share" in body
    assert "the URL is the scenario" in body


def test_choosing_no_consumption_says_so_rather_than_showing_nothing(
    client: Client,
) -> None:
    body = text_of(client.get(f"/explore/?standard={NO_CONSUMPTION}"))
    assert "Nothing is being consumed" in body


def test_the_branch_from_the_page_applies_cleanly() -> None:
    """Whatever the interface shows must be reconstructible from its branch
    alone, since that is what gets shared and exported."""
    params = _params(alfalfa="60", periods="4")
    branch = params.to_branch()
    from pdc.seed.scenarios import allocation_for, reference_plans
    from pdc.sim import Scenario

    base = Scenario(
        "baseline", allocation_for(0.0, "baseline"), reference_plans(), 4, CONSUMPTION_STANDARD
    )
    assert apply_branch(base, branch) == params.to_scenario()
