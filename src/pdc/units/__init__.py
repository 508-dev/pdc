"""Dimensioned quantities with substance-aware types."""

from pdc.units.registry import Q, Quantity, build_registry, ureg
from pdc.units.substances import (
    dry_to_fresh,
    fresh_to_dry,
    k2o_to_k,
    k_to_k2o,
    n_to_crude_protein,
    p2o5_to_p,
    p_to_p2o5,
)

__all__ = [
    "Q",
    "Quantity",
    "build_registry",
    "dry_to_fresh",
    "fresh_to_dry",
    "k2o_to_k",
    "k_to_k2o",
    "n_to_crude_protein",
    "p2o5_to_p",
    "p_to_p2o5",
    "ureg",
]
