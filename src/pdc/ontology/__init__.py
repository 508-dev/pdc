"""Valueflows v1.0.0 entities, adopted as PDC's ontology."""

from pdc.ontology.actions import BEHAVIOUR, IO, Action, ActionBehaviour, Effect
from pdc.ontology.citation import Citation, Coefficient, Provenance
from pdc.ontology.core import (
    Agent,
    AgentKind,
    EconomicResource,
    ProcessSpecification,
    RecipeFlow,
    RecipeProcess,
    ResourceSpecification,
)

__all__ = [
    "BEHAVIOUR",
    "IO",
    "Action",
    "ActionBehaviour",
    "Agent",
    "AgentKind",
    "Citation",
    "Coefficient",
    "EconomicResource",
    "Effect",
    "ProcessSpecification",
    "Provenance",
    "RecipeFlow",
    "RecipeProcess",
    "ResourceSpecification",
]
