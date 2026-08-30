"""Explicit, named conversions between substance conventions.

These exist so that a conversion is always a visible act. There is
deliberately no pint context and no implicit coercion: converting P2O5 to
elemental P is a modelling decision that should appear in a diff, not
something that happens because two numbers met in an expression.

See DECISIONS.md D-013.
"""

from __future__ import annotations

import pint

from pdc.units.registry import (
    DEFAULT_N_TO_PROTEIN,
    K2O_TO_K,
    P2O5_TO_P,
    ureg,
)


def p2o5_to_p(quantity: pint.Quantity) -> pint.Quantity:
    """Convert a phosphorus-pentoxide mass to elemental phosphorus (x0.4364)."""
    kg = quantity.to("kgP2O5").magnitude
    return ureg.Quantity(kg * P2O5_TO_P, "kgP")


def p_to_p2o5(quantity: pint.Quantity) -> pint.Quantity:
    """Convert an elemental-phosphorus mass to P2O5 (x2.2914)."""
    kg = quantity.to("kgP").magnitude
    return ureg.Quantity(kg / P2O5_TO_P, "kgP2O5")


def k2o_to_k(quantity: pint.Quantity) -> pint.Quantity:
    """Convert a potassium-oxide mass to elemental potassium (x0.8301)."""
    kg = quantity.to("kgK2O").magnitude
    return ureg.Quantity(kg * K2O_TO_K, "kgK")


def k_to_k2o(quantity: pint.Quantity) -> pint.Quantity:
    """Convert an elemental-potassium mass to K2O (x1.2047)."""
    kg = quantity.to("kgK").magnitude
    return ureg.Quantity(kg / K2O_TO_K, "kgK2O")


def n_to_crude_protein(
    quantity: pint.Quantity, factor: float = DEFAULT_N_TO_PROTEIN
) -> pint.Quantity:
    """Convert nitrogen to crude protein by an explicit Jones factor.

    The factor is a convention rather than chemistry. 6.25 is the general
    default; wheat is conventionally 5.70 and milk 6.38. Pass the right one
    for the foodstuff, and record which you used.
    """
    kg = quantity.to("kgN").magnitude
    return ureg.Quantity(kg * factor, "kgProtein")


def fresh_to_dry(quantity: pint.Quantity, dry_matter_fraction: float) -> pint.Quantity:
    """Convert fresh weight to dry matter at a crop-specific fraction.

    The fraction is never a default. Fresh silage is around 0.20 and hay
    around 0.90; guessing moves a feed model by a factor of four.
    """
    if not 0.0 < dry_matter_fraction <= 1.0:
        raise ValueError(f"dry matter fraction must be in (0, 1], got {dry_matter_fraction}")
    kg = quantity.to("kgFW").magnitude
    return ureg.Quantity(kg * dry_matter_fraction, "kgDM")


def dry_to_fresh(quantity: pint.Quantity, dry_matter_fraction: float) -> pint.Quantity:
    """Convert dry matter to fresh weight at a crop-specific fraction."""
    if not 0.0 < dry_matter_fraction <= 1.0:
        raise ValueError(f"dry matter fraction must be in (0, 1], got {dry_matter_fraction}")
    kg = quantity.to("kgDM").magnitude
    return ureg.Quantity(kg / dry_matter_fraction, "kgFW")
