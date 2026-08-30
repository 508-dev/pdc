"""Unit registry with substance-aware nutrient and biomass types.

Everything above the units layer is dimensioned. The non-obvious part is that
some quantities which look like "a mass" must not be interchangeable with each
other, because the literature reports them under different conventions and the
conversion is large enough to invalidate a model silently.

The classic trap is phosphorus. Agronomy and fertiliser labelling report
phosphorus as P2O5; soil science and nutrition report elemental P. The two
differ by a factor of 2.29. A model that mixes them overstates phosphorus by
more than double and every downstream number still looks plausible.

So these are given distinct dimensions and *refuse to add*. Conversion is
possible but must be spelled: see ``pdc.units.substances``.

See DECISIONS.md D-013 and docs/architecture.md section 2.
"""

from __future__ import annotations

import pint

# Ratios are molar-mass derived and exact to the precision given.
#
#   P2O5 -> P    2 x 30.974 / 141.945 = 0.436421
#   K2O  -> K    2 x 39.098 / 94.196  = 0.830075
#   N    -> crude protein             = 6.25 (Jones factor, general default)
#
# The nitrogen-to-protein factor is a convention, not chemistry: 6.25 assumes
# 16% nitrogen in protein and is wrong for several foodstuffs (wheat is
# conventionally 5.70, milk 6.38). It is exposed as a parameter rather than
# baked in, for that reason.
P2O5_TO_P = 0.436421
K2O_TO_K = 0.830075
DEFAULT_N_TO_PROTEIN = 6.25

_DEFINITIONS = """
# --- Substance-aware nutrient masses -------------------------------------
# Independent dimensions on purpose. kgP + kgP2O5 must raise.

kgP = [mass_phosphorus_elemental] = kg_P
gP = kgP / 1000 = g_P
tP = 1000 * kgP = t_P

kgP2O5 = [mass_phosphorus_pentoxide] = kg_P2O5
gP2O5 = kgP2O5 / 1000 = g_P2O5

kgK = [mass_potassium_elemental] = kg_K
gK = kgK / 1000 = g_K

kgK2O = [mass_potassium_oxide] = kg_K2O
gK2O = kgK2O / 1000 = g_K2O

kgN = [mass_nitrogen_elemental] = kg_N
gN = kgN / 1000 = g_N

kgProtein = [mass_crude_protein] = kg_protein
gProtein = kgProtein / 1000 = g_protein

# --- Biomass basis --------------------------------------------------------
# Forage and feed yields are quoted both as fresh weight and as dry matter.
# The ratio runs from roughly 0.20 (fresh silage) to 0.90 (hay), so confusing
# them moves a livestock model by a factor of four. Crop-specific conversion
# lives in pdc.units.substances.

kgDM = [mass_dry_matter] = kg_DM
tDM = 1000 * kgDM = t_DM

kgFW = [mass_fresh_weight] = kg_FW
tFW = 1000 * kgFW = t_FW

# --- Labour ---------------------------------------------------------------
# Labour is an effort quantity attached to a `work` flow, not a resource that
# moves around (Valueflows treats it this way and it is the right treatment).
# Typed separately from wall-clock hours so that a duration cannot be added to
# an effort.

labour_hour = [labour_effort] = lab_h
labour_day = 8 * labour_hour = lab_d

# --- Land -----------------------------------------------------------------
# Land occupied for a growing season. Distinct from bare area because the
# scarce thing is area-time, not area.

hectare_season = [land_occupation] = ha_season
"""


def build_registry() -> pint.UnitRegistry:
    """Construct the PDC unit registry.

    A fresh registry rather than pint's application registry: the kernel must
    not depend on global mutable state, because determinism is a hard
    requirement (D-005) and a shared registry is exactly the kind of thing
    that makes results depend on import order.
    """
    registry: pint.UnitRegistry = pint.UnitRegistry(autoconvert_offset_to_baseunit=False)
    registry.load_definitions(_DEFINITIONS.splitlines())
    # Compact display by default. Formatting only; nothing in the kernel
    # depends on it.
    registry.formatter.default_format = "~P"
    return registry


ureg = build_registry()
Quantity = ureg.Quantity


def Q(value: float, unit: str) -> pint.Quantity:
    """Shorthand for a dimensioned quantity in the PDC registry."""
    return ureg.Quantity(value, unit)
