"""Coefficient table for the synthetic reference region.

READ THIS BEFORE REUSING ANY NUMBER HERE.

This table exists to make the reference region behave plausibly, not to be
authoritative. Most entries are marked ILLUSTRATIVE, which means they are
representative values chosen to be in the right range and are **not** valid in
a model anyone relies on. ``Coefficient.check_usable()`` will refuse them.

Entries marked PUBLISHED name a real, checkable source, but most still lack a
precise locator (table, page, edition). Confirming those — and replacing the
illustrative ones with sourced figures for an actual region — is the single
most useful contribution to this project. See CONTRIBUTING.md.

The point of the provenance machinery is that this warning is enforced by the
type system rather than by a comment nobody reads.
"""

from __future__ import annotations

from pdc.ontology.citation import Citation, Coefficient, Provenance
from pdc.units import Q

# --------------------------------------------------------------------------
# Citations
# --------------------------------------------------------------------------

SPHERE = Citation(
    source="The Sphere Handbook: Humanitarian Charter and Minimum Standards, 2018 edition",
    provenance=Provenance.PUBLISHED,
    locator="Food Security and Nutrition chapter",
    note=(
        "2,100 kcal/person/day, 10-12% of energy from protein, 17% from fat, "
        "plus micronutrient adequacy. A survival minimum for a displaced "
        "population, not a target for ordinary life."
    ),
)

USDA_FDC = Citation(
    source="USDA FoodData Central (Foundation Foods / SR Legacy)",
    provenance=Provenance.PUBLISHED,
    locator="fdc.nal.usda.gov",
    note="Composition figures are standard reference values; confirm the exact food code.",
)

FIXTURE = Citation(
    source="PDC synthetic reference region",
    provenance=Provenance.ILLUSTRATIVE,
    note=(
        "Chosen to be plausible for a temperate, partly irrigated, "
        "semi-mechanised mixed farming region. Not measured, not sourced. "
        "Fixtures only."
    ),
)

STOICHIOMETRY = Citation(
    source="Molar mass ratio",
    provenance=Provenance.PUBLISHED,
    locator="P2O5 -> P = 2 x 30.974 / 141.945",
    note="Exact by definition; not an empirical measurement.",
)


def _fixture(name: str, value: object, note: str) -> Coefficient:
    """A fixture coefficient, explicitly marked illustrative."""
    from dataclasses import replace

    return Coefficient(
        name=name,
        value=value,  # type: ignore[arg-type]
        citation=replace(FIXTURE, note=f"{FIXTURE.note} {note}"),
    )


# --------------------------------------------------------------------------
# Human requirement
# --------------------------------------------------------------------------

SURVIVAL_ENERGY = Coefficient(
    name="human.energy.survival",
    value=Q(2100.0, "kcal/day"),
    citation=SPHERE,
    tags=("need", "energy"),
)

ADEQUATE_ENERGY = _fixture(
    "human.energy.adequate",
    Q(2500.0, "kcal/day"),
    "A comfortable rather than minimum intake for a mixed-activity adult population.",
)

# --------------------------------------------------------------------------
# Crop yields, per hectare-season
# --------------------------------------------------------------------------

WHEAT_YIELD = _fixture(
    "wheat.yield",
    Q(3.0, "tFW/ha_season"),
    "Rainfed temperate wheat. World average is nearer 3.5 t/ha (FAOSTAT); "
    "3.0 is deliberately conservative for a region without synthetic inputs.",
)

POTATO_YIELD = _fixture(
    "potato.yield",
    Q(20.0, "tFW/ha_season"),
    "Fresh tubers. World average is around 21 t/ha (FAOSTAT).",
)

ALFALFA_YIELD = _fixture(
    "alfalfa.yield",
    Q(9.0, "tDM/ha_season"),
    "Dry matter, partly irrigated. Fully irrigated stands reach 12-15 t DM/ha; "
    "rainfed 6-8. Note this is DM, not fresh weight - the difference is a "
    "factor of four and is the classic way a forage model goes wrong.",
)

# --------------------------------------------------------------------------
# Phosphorus removal
#
# This is the coefficient the reference question turns on. Agronomic sources
# report removal as P2O5; the model carries elemental P. The conversion is
# ×2.29 and doing it implicitly would overstate the phosphorus budget by more
# than double while every downstream number still looked reasonable.
# --------------------------------------------------------------------------

WHEAT_P_REMOVAL = _fixture(
    "wheat.phosphorus_removal",
    Q(3.5, "kgP/tFW"),
    "Grain phosphorus removal. Agronomic tables quote roughly 8 kg P2O5 per "
    "tonne of grain, which is 3.49 kg elemental P. Straw removal is excluded: "
    "this region returns straw to the field.",
)

POTATO_P_REMOVAL = _fixture(
    "potato.phosphorus_removal",
    Q(0.52, "kgP/tFW"),
    "Tuber phosphorus removal, roughly 1.2 kg P2O5 per tonne of fresh tubers.",
)

ALFALFA_P_REMOVAL = _fixture(
    "alfalfa.phosphorus_removal",
    Q(2.5, "kgP/tDM"),
    "Roughly 5.7 kg P2O5 per tonne DM. Alfalfa is a heavy phosphorus feeder, "
    "which is why it competes with grain for the same limited supply.",
)

# --------------------------------------------------------------------------
# Water
# --------------------------------------------------------------------------

WHEAT_WATER = _fixture(
    "wheat.water", Q(4500.0, "m^3/ha_season"), "About 450 mm over a growing season."
)
POTATO_WATER = _fixture("potato.water", Q(5000.0, "m^3/ha_season"), "About 500 mm.")
ALFALFA_WATER = _fixture(
    "alfalfa.water",
    Q(9000.0, "m^3/ha_season"),
    "About 900 mm. Alfalfa is famously thirsty; it competes for water as well "
    "as phosphorus, so the two constraints can bind in either order.",
)

# --------------------------------------------------------------------------
# Labour
# --------------------------------------------------------------------------

WHEAT_LABOUR = _fixture(
    "wheat.labour",
    Q(25.0, "labour_hour/ha_season"),
    "Semi-mechanised. Fully mechanised is nearer 10 h/ha; hand cultivation exceeds 100.",
)
POTATO_LABOUR = _fixture(
    "potato.labour", Q(120.0, "labour_hour/ha_season"), "Considerably more hand work."
)
ALFALFA_LABOUR = _fixture(
    "alfalfa.labour", Q(15.0, "labour_hour/ha_season"), "Cutting and baling, several cuts."
)
DAIRY_LABOUR = _fixture(
    "dairy.labour", Q(40.0, "labour_hour/year"), "Per cow per year, pasture-based."
)

# --------------------------------------------------------------------------
# Processing
# --------------------------------------------------------------------------

FLOUR_EXTRACTION = _fixture(
    "milling.extraction_rate",
    Q(0.78, "kgFW/kgFW"),
    "White flour extraction. Wholemeal approaches 1.0; the bran fraction "
    "becomes livestock feed rather than being lost.",
)
BREAD_YIELD = _fixture(
    "baking.yield",
    Q(1.5, "kgFW/kgFW"),
    "Bread per unit flour, the difference being absorbed water.",
)
MILL_LABOUR = _fixture("milling.labour", Q(0.9, "labour_hour/tFW"), "Per tonne of grain milled.")
BAKE_LABOUR = _fixture("baking.labour", Q(8.0, "labour_hour/tFW"), "Per tonne of bread.")

# --------------------------------------------------------------------------
# Livestock
# --------------------------------------------------------------------------

MILK_YIELD = _fixture(
    "dairy.milk_yield",
    Q(5500.0, "kgFW/year"),
    "Per cow per year, forage-based rather than high-input confinement, where "
    "10,000 kg is achievable.",
)
COW_FEED = _fixture(
    "dairy.feed_requirement",
    Q(5500.0, "kgDM/year"),
    "Total dry matter intake per cow per year, of which the alfalfa fraction "
    "is modelled separately.",
)
COW_ALFALFA_FRACTION = _fixture(
    "dairy.alfalfa_fraction",
    Q(0.40, "kgDM/kgDM"),
    "Alfalfa share of dry matter intake; the remainder is pasture and "
    "crop residue, which are not phosphorus-limited here.",
)

# --------------------------------------------------------------------------
# Food energy content
# --------------------------------------------------------------------------

GRAIN_ENERGY = Coefficient(
    name="wheat.grain.energy",
    value=Q(3400.0, "kcal/kgFW"),
    citation=USDA_FDC,
    tags=("composition", "energy"),
)
"""Whole wheat grain. Note this exceeds the energy of the bread made from it:
milling to white flour removes the bran, and baking adds water. Milling is a
choice about palatability and storage, not a free improvement, and the model
should show that rather than hide it."""

BREAD_ENERGY = Coefficient(
    name="bread.energy",
    value=Q(2470.0, "kcal/kgFW"),
    citation=USDA_FDC,
    tags=("composition", "energy"),
)
POTATO_ENERGY = Coefficient(
    name="potato.energy",
    value=Q(770.0, "kcal/kgFW"),
    citation=USDA_FDC,
    tags=("composition", "energy"),
)
MILK_ENERGY = Coefficient(
    name="milk.energy",
    value=Q(610.0, "kcal/kgFW"),
    citation=USDA_FDC,
    tags=("composition", "energy"),
)

ALL: tuple[Coefficient, ...] = (
    SURVIVAL_ENERGY,
    ADEQUATE_ENERGY,
    WHEAT_YIELD,
    POTATO_YIELD,
    ALFALFA_YIELD,
    WHEAT_P_REMOVAL,
    POTATO_P_REMOVAL,
    ALFALFA_P_REMOVAL,
    WHEAT_WATER,
    POTATO_WATER,
    ALFALFA_WATER,
    WHEAT_LABOUR,
    POTATO_LABOUR,
    ALFALFA_LABOUR,
    DAIRY_LABOUR,
    FLOUR_EXTRACTION,
    BREAD_YIELD,
    MILL_LABOUR,
    BAKE_LABOUR,
    MILK_YIELD,
    COW_FEED,
    COW_ALFALFA_FRACTION,
    GRAIN_ENERGY,
    BREAD_ENERGY,
    POTATO_ENERGY,
    MILK_ENERGY,
)
