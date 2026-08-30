"""Substance-aware units must refuse the conversions that sink real models."""

from __future__ import annotations

import pint
import pytest

from pdc.units import (
    Q,
    dry_to_fresh,
    fresh_to_dry,
    k2o_to_k,
    n_to_crude_protein,
    p2o5_to_p,
    p_to_p2o5,
)


def test_phosphorus_conventions_refuse_to_add() -> None:
    """The Gimli Glider case: two numbers that look like the same quantity.

    Agronomy reports P2O5, soil science reports elemental P, and they differ
    by 2.29x. Silently adding them overstates phosphorus by more than double
    while every downstream number still looks plausible.
    """
    with pytest.raises(pint.DimensionalityError):
        _ = Q(1.0, "kgP") + Q(1.0, "kgP2O5")


def test_potassium_and_nitrogen_conventions_also_refuse() -> None:
    with pytest.raises(pint.DimensionalityError):
        _ = Q(1.0, "kgK") + Q(1.0, "kgK2O")
    with pytest.raises(pint.DimensionalityError):
        _ = Q(1.0, "kgN") + Q(1.0, "kgProtein")


def test_dry_matter_and_fresh_weight_refuse() -> None:
    """Confusing these moves a livestock model by a factor of four."""
    with pytest.raises(pint.DimensionalityError):
        _ = Q(1.0, "kgDM") + Q(1.0, "kgFW")


def test_labour_effort_is_not_a_duration() -> None:
    """Ten labour-hours is not ten hours elapsed: five people for two hours is
    also ten labour-hours. Adding them is a category error."""
    with pytest.raises(pint.DimensionalityError):
        _ = Q(1.0, "labour_hour") + Q(1.0, "hour")


def test_explicit_phosphorus_conversion_is_correct() -> None:
    converted = p2o5_to_p(Q(8.0, "kgP2O5"))
    assert converted.units == Q(1.0, "kgP").units
    assert converted.magnitude == pytest.approx(3.4914, rel=1e-4)


def test_phosphorus_conversion_round_trips() -> None:
    original = Q(3.5, "kgP")
    assert p2o5_to_p(p_to_p2o5(original)).magnitude == pytest.approx(3.5, rel=1e-9)


def test_potassium_conversion_is_correct() -> None:
    assert k2o_to_k(Q(1.0, "kgK2O")).magnitude == pytest.approx(0.8301, rel=1e-4)


def test_nitrogen_to_protein_factor_is_explicit() -> None:
    """6.25 is a convention, not chemistry. Wheat is conventionally 5.70."""
    assert n_to_crude_protein(Q(1.0, "kgN")).magnitude == pytest.approx(6.25)
    assert n_to_crude_protein(Q(1.0, "kgN"), factor=5.70).magnitude == pytest.approx(5.70)


def test_dry_matter_conversion_requires_a_fraction() -> None:
    assert fresh_to_dry(Q(10.0, "kgFW"), 0.20).magnitude == pytest.approx(2.0)
    assert dry_to_fresh(Q(2.0, "kgDM"), 0.20).magnitude == pytest.approx(10.0)


@pytest.mark.parametrize("fraction", [0.0, -0.1, 1.5])
def test_dry_matter_fraction_is_validated(fraction: float) -> None:
    with pytest.raises(ValueError, match="dry matter fraction"):
        fresh_to_dry(Q(1.0, "kgFW"), fraction)
