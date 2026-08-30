"""Determinism guarantees.

D-005 makes reproducibility a hard requirement rather than a nicety: it is the
mechanism by which someone runs a scenario against their own mirror and finds
out exactly where their model and yours disagree. If these tests fail,
something in the kernel became order- or clock-dependent and the auditability
argument no longer holds.

Per CONTRIBUTING.md these must never be skipped or marked xfail.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from pdc.needs import to_json
from pdc.seed import build_reference_region

pytestmark = pytest.mark.determinism


def _fingerprint() -> str:
    """A stable serialisation of everything the region computes.

    Deliberately covers agents, stocks, recipe coefficients, and evaluated
    need — the values a second implementation would have to match.
    """
    region = build_reference_region()
    payload = {
        "agents": [
            {
                "id": a.id,
                "kind": a.kind,
                "member_of": a.member_of,
                "attributes": [[k, v] for k, v in a.attributes],
            }
            for a in sorted(region.agents, key=lambda a: a.id)
        ],
        "resources": [
            {
                "id": r.id,
                "specification": r.specification_id,
                "custodian": r.custodian_id,
                "magnitude": float(r.quantity.magnitude),
                "units": str(r.quantity.units),
            }
            for r in sorted(region.resources, key=lambda r: r.id)
        ],
        "recipes": [
            {
                "id": rec.id,
                "flows": [
                    {
                        "action": f.action.value,
                        "specification": f.specification_id,
                        "magnitude": float(f.quantity.magnitude),
                        "units": str(f.quantity.units),
                        "lag": f.lag_periods,
                    }
                    for f in rec.flows()
                ],
            }
            for rec in sorted(region.recipes, key=lambda r: r.id)
        ],
        "standards": [
            {
                "id": s.id,
                "expression": to_json(s.expression),
                "evaluated": {
                    a.id: float(s.evaluate(a).to("kcal/day").magnitude)
                    for a in sorted(region.agents, key=lambda a: a.id)
                    if a.kind == "commune"
                },
            }
            for s in sorted(region.standards, key=lambda s: s.id)
        ],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def test_building_the_region_twice_gives_identical_results() -> None:
    assert _fingerprint() == _fingerprint()


def test_agent_attributes_are_deterministically_ordered() -> None:
    """An unordered structure feeding computation is the exact class of bug
    this guarantee exists to prevent."""
    region = build_reference_region()
    for agent in region.agents:
        assert list(agent.attributes) == sorted(agent.attributes)


def test_results_are_identical_under_a_different_hash_seed() -> None:
    """The real test. PYTHONHASHSEED changes set and dict iteration order, so
    any hidden dependence on it shows up here and nowhere else."""
    script = (
        "import sys; sys.path.insert(0, 'tests');"
        "from test_determinism import _fingerprint; print(_fingerprint())"
    )

    def run(seed: str) -> str:
        environment = dict(os.environ, PYTHONHASHSEED=seed)
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=True,
            env=environment,
        )
        return result.stdout.strip()

    assert run("0") == run("12345") == _fingerprint()
