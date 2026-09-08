"""Simulation: branched worlds, forward propagation, and explanations."""

from pdc.sim.branch import Assumption, AssumptionKind, Branch, apply_branch
from pdc.sim.explain import Cause, CauseKind, Evidence, render_text
from pdc.sim.export import (
    EXPORT_FORMAT,
    CoefficientDifference,
    Verification,
    build_export,
    diff_recipes,
    is_diffable,
    recipes_digest,
    recipes_payload,
    results_json,
    standards_digest,
    standards_payload,
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
    "CoefficientDifference",
    "Verification",
    "apply_branch",
    "build_export",
    "canonical_json",
    "diff_recipes",
    "is_diffable",
    "digest",
    "recipes_digest",
    "recipes_payload",
    "results_json",
    "short",
    "standards_digest",
    "standards_payload",
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
