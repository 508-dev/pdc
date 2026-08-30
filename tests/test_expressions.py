"""The expression language: total, unit-aware, and cheap to reimplement."""

from __future__ import annotations

import pytest

from pdc.needs import (
    Attr,
    BinOp,
    BracketSum,
    Clamp,
    ExpressionError,
    If,
    Lit,
    NAry,
    NeedStandard,
    Ref,
    evaluate,
    evaluate_quantity,
    from_json,
    to_json,
)
from pdc.ontology import Agent, Citation, Provenance

CITATION = Citation("a test", Provenance.ILLUSTRATIVE)


def _agent(**attributes: float) -> Agent:
    return Agent("t", "Test", "commune", attributes=tuple(attributes.items()))


def test_population_times_a_rate() -> None:
    expression = BinOp("mul", Attr("population"), Lit(2100.0, "kcal/day"))
    result = evaluate_quantity(expression, _agent(population=12000.0))
    assert result.to("kcal/day").magnitude == pytest.approx(25_200_000.0)


def test_missing_attribute_fails_loudly() -> None:
    """Never a silent zero. A defaulted attribute in a needs calculation is
    the worst available failure mode."""
    with pytest.raises(KeyError, match="rainfall"):
        evaluate(Attr("rainfall"), _agent(population=100.0))


def test_dimensional_mismatch_is_an_error() -> None:
    """Adding phosphorus to labour is forbidden by D-002; the units layer is
    what enforces it, and the expression layer surfaces it."""
    expression = BinOp("add", Lit(1.0, "kgP"), Lit(1.0, "labour_hour"))
    with pytest.raises(ExpressionError, match="dimensional error"):
        evaluate(expression, _agent())


def test_conditional_and_comparison() -> None:
    expression = If(
        BinOp("gt", Attr("population"), Lit(1000.0, "dimensionless")),
        Lit(2.0, "kcal"),
        Lit(1.0, "kcal"),
    )
    assert evaluate_quantity(expression, _agent(population=5000.0)).magnitude == pytest.approx(2.0)
    assert evaluate_quantity(expression, _agent(population=10.0)).magnitude == pytest.approx(1.0)


def test_min_max_and_clamp() -> None:
    assert evaluate_quantity(
        NAry("min", (Lit(3.0, "kcal"), Lit(1.0, "kcal"), Lit(2.0, "kcal"))), _agent()
    ).magnitude == pytest.approx(1.0)
    assert evaluate_quantity(
        Clamp(Lit(9.0, "kcal"), Lit(1.0, "kcal"), Lit(5.0, "kcal")), _agent()
    ).magnitude == pytest.approx(5.0)


def test_bracket_sum_is_bounded_iteration() -> None:
    """The only repetition construct, and it iterates over a finite table."""
    agent = _agent(
        **{
            "population.age.0_4": 900.0,
            "population.age.5_14": 2100.0,
            "population.age.15_64": 7600.0,
            "population.age.65_plus": 1400.0,
        }
    )
    expression = BracketSum(
        over="population.age",
        bind="bracket",
        body=BinOp("mul", Attr("bracket"), Lit(2100.0, "kcal/day")),
    )
    result = evaluate_quantity(expression, agent)
    assert result.to("kcal/day").magnitude == pytest.approx(12000.0 * 2100.0)


def test_bracket_sum_requires_the_table_to_exist() -> None:
    with pytest.raises(ExpressionError, match="no bracket table"):
        evaluate(BracketSum("population.age", "b", Attr("b")), _agent(population=1.0))


def test_standard_references_resolve() -> None:
    base = NeedStandard("base", "Base", "a", CITATION, "1", Lit(1000.0, "kcal/day"), "food.energy")
    derived = BinOp("mul", Ref("base"), Lit(2.0, "dimensionless"))
    result = evaluate_quantity(derived, _agent(), standards={"base": base})
    assert result.to("kcal/day").magnitude == pytest.approx(2000.0)


def test_cyclic_references_are_rejected() -> None:
    """Standards form a DAG. A cycle is caught rather than hanging."""
    a = NeedStandard("a", "A", "x", CITATION, "1", Ref("b"), "food.energy")
    b = NeedStandard("b", "B", "x", CITATION, "1", Ref("a"), "food.energy")
    with pytest.raises(ExpressionError, match="cyclic"):
        evaluate(Ref("a"), _agent(), standards={"a": a, "b": b})


def test_unresolved_reference_is_an_error() -> None:
    with pytest.raises(ExpressionError, match="unresolved"):
        evaluate(Ref("nope"), _agent(), standards={})


@pytest.mark.parametrize(
    "expression",
    [
        Lit(1.0, "kcal"),
        Attr("population"),
        BinOp("mul", Attr("population"), Lit(2100.0, "kcal/day")),
        NAry("max", (Lit(1.0, "kcal"), Lit(2.0, "kcal"))),
        Clamp(Lit(1.0, "kcal"), Lit(0.0, "kcal"), Lit(2.0, "kcal")),
        If(BinOp("lt", Lit(1.0, "kcal"), Lit(2.0, "kcal")), Lit(1.0, "kcal"), Lit(2.0, "kcal")),
        BracketSum("population.age", "b", Attr("b")),
        Ref("other"),
    ],
)
def test_json_round_trip(expression: object) -> None:
    """The wire format is the specification: anyone reimplementing the
    evaluator implements against this and nothing else."""
    assert to_json(from_json(to_json(expression))) == to_json(expression)  # type: ignore[arg-type]


def test_unknown_operator_is_rejected() -> None:
    with pytest.raises(ExpressionError, match="unknown operator"):
        from_json({"op": "exec", "cmd": "rm -rf /"})
