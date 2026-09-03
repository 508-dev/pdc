"""Simulation: branched worlds, forward propagation, and explanations."""

from pdc.sim.branch import Assumption, AssumptionKind, Branch, apply_branch
from pdc.sim.explain import Cause, CauseKind, Evidence, render_text
from pdc.sim.export import (
    EXPORT_FORMAT,
    Verification,
    build_export,
    recipes_digest,
    results_json,
    standards_digest,
    verify,
)
from pdc.sim.forward import (
    ForwardRun,
    NeedOutcome,
    PeriodResult,
    ProcessOutcome,
    run_forward,
)
from pdc.sim.identity import canonical_json, digest, short
from pdc.sim.world import (
    Allocation,
    ProcessPlan,
    Scenario,
    StockKey,
    WorldState,
    recipes_by_id,
)

__all__ = [
    "EXPORT_FORMAT",
    "Assumption",
    "AssumptionKind",
    "Branch",
    "Verification",
    "apply_branch",
    "build_export",
    "canonical_json",
    "digest",
    "recipes_digest",
    "results_json",
    "short",
    "standards_digest",
    "verify",
    "Allocation",
    "Cause",
    "CauseKind",
    "Evidence",
    "ForwardRun",
    "NeedOutcome",
    "PeriodResult",
    "ProcessOutcome",
    "ProcessPlan",
    "Scenario",
    "StockKey",
    "WorldState",
    "recipes_by_id",
    "render_text",
    "run_forward",
]
