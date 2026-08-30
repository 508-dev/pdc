"""The need-standard expression language.

Total, pure, deterministic, unit-aware, serialisable as a JSON AST. No loops,
no recursion, no user-defined functions, no I/O. Every expression terminates.

The restriction is not purity for its own sake. It exists to make a *second
implementation cheap* (D-007). If a standard were Python, verifying it would
mean running our Python, with our interpreter and our dependency tree, and
independent verification would collapse into trusting our toolchain. As a
twenty-node expression tree it can be re-derived in Rust, in a spreadsheet, or
on paper in an afternoon.

That is the whole auditability model, so this evaluator is deliberately kept
small enough to reimplement in a weekend. Keep it that way.

Smart contracts are the cautionary tale, not the template: Turing-completeness
produced a world where nobody reads the contract and verification is
outsourced to audit firms.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import pint

from pdc.units import ureg


class ExpressionError(Exception):
    """Raised for a malformed, cyclic, or non-evaluable expression."""


@runtime_checkable
class AttributeSource(Protocol):
    """Anything expressions can read attributes from — normally an Agent."""

    def attribute(self, path: str) -> float: ...
    def has_attribute(self, path: str) -> bool: ...


Value = pint.Quantity | bool


# --------------------------------------------------------------------------
# Nodes
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Lit:
    """A unit-tagged literal. ``{"op": "lit", "value": 2300, "unit": "kcal/day"}``"""

    value: float
    unit: str


@dataclass(frozen=True, slots=True)
class Attr:
    """Reads an agent attribute. Missing attributes raise; never default."""

    path: str
    unit: str = "dimensionless"


@dataclass(frozen=True, slots=True)
class BinOp:
    """add | sub | mul | div, and the comparisons lt | lte | gt | gte | eq."""

    op: str
    left: Node
    right: Node


@dataclass(frozen=True, slots=True)
class NAry:
    """min | max over two or more operands."""

    op: str
    operands: tuple[Node, ...]


@dataclass(frozen=True, slots=True)
class Clamp:
    value: Node
    lo: Node
    hi: Node


@dataclass(frozen=True, slots=True)
class If:
    cond: Node
    then: Node
    otherwise: Node


@dataclass(frozen=True, slots=True)
class BracketSum:
    """Bounded summation over a declared attribute table.

    Sums ``body`` over each bracket in the table named by ``over``, binding
    the bracket's value to ``bind``. Population by age-sex bracket is the
    motivating case.

    Bounded, not iterative: the table has a known finite size declared in the
    agent's attributes, so termination is guaranteed. This is the only
    repetition construct in the language and the only one there will be.
    """

    over: str
    bind: str
    body: Node


@dataclass(frozen=True, slots=True)
class Ref:
    """References another standard's result.

    Standards form a DAG. Cycles are rejected at validation, not discovered at
    evaluation.
    """

    standard_id: str


Node = Lit | Attr | BinOp | NAry | Clamp | If | BracketSum | Ref

_ARITHMETIC = {"add", "sub", "mul", "div"}
_COMPARISON = {"lt", "lte", "gt", "gte", "eq"}


# --------------------------------------------------------------------------
# Evaluation
# --------------------------------------------------------------------------


def evaluate(
    node: Node,
    agent: AttributeSource,
    *,
    bindings: dict[str, pint.Quantity] | None = None,
    standards: dict[str, Any] | None = None,
    _stack: tuple[str, ...] = (),
) -> Value:
    """Evaluate an expression against an agent.

    ``standards`` maps standard id to NeedStandard for ``Ref`` resolution.
    ``_stack`` carries the reference chain for cycle detection.
    """
    bindings = bindings or {}

    match node:
        case Lit(value, unit):
            return ureg.Quantity(value, unit)

        case Attr(path, unit):
            if path in bindings:
                return bindings[path]
            return ureg.Quantity(agent.attribute(path), unit)

        case BinOp(op, left, right):
            lhs = evaluate(left, agent, bindings=bindings, standards=standards, _stack=_stack)
            rhs = evaluate(right, agent, bindings=bindings, standards=standards, _stack=_stack)
            return _apply_binop(op, lhs, rhs)

        case NAry(op, operands):
            values = [
                evaluate(o, agent, bindings=bindings, standards=standards, _stack=_stack)
                for o in operands
            ]
            if op == "min":
                return min(values)
            if op == "max":
                return max(values)
            raise ExpressionError(f"unknown n-ary operator {op!r}")

        case Clamp(value, lo, hi):
            v = evaluate(value, agent, bindings=bindings, standards=standards, _stack=_stack)
            low = evaluate(lo, agent, bindings=bindings, standards=standards, _stack=_stack)
            high = evaluate(hi, agent, bindings=bindings, standards=standards, _stack=_stack)
            return min(max(v, low), high)

        case If(cond, then, otherwise):
            test = evaluate(cond, agent, bindings=bindings, standards=standards, _stack=_stack)
            if not isinstance(test, bool):
                raise ExpressionError("`if` condition must evaluate to a boolean")
            branch = then if test else otherwise
            return evaluate(branch, agent, bindings=bindings, standards=standards, _stack=_stack)

        case BracketSum(over, bind, body):
            return _bracket_sum(node, over, bind, body, agent, bindings, standards, _stack)

        case Ref(standard_id):
            if standards is None or standard_id not in standards:
                raise ExpressionError(f"unresolved standard reference {standard_id!r}")
            if standard_id in _stack:
                cycle = " -> ".join((*_stack, standard_id))
                raise ExpressionError(f"cyclic standard reference: {cycle}")
            referenced = standards[standard_id]
            return evaluate(
                referenced.expression,
                agent,
                bindings=bindings,
                standards=standards,
                _stack=(*_stack, standard_id),
            )

    raise ExpressionError(f"unknown node type {type(node).__name__}")


def _apply_binop(op: str, lhs: Value, rhs: Value) -> Value:
    if op in _COMPARISON:
        if op == "lt":
            return bool(lhs < rhs)
        if op == "lte":
            return bool(lhs <= rhs)
        if op == "gt":
            return bool(lhs > rhs)
        if op == "gte":
            return bool(lhs >= rhs)
        return bool(lhs == rhs)

    if op not in _ARITHMETIC:
        raise ExpressionError(f"unknown binary operator {op!r}")
    if isinstance(lhs, bool) or isinstance(rhs, bool):
        raise ExpressionError(f"cannot apply {op!r} to a boolean")

    try:
        if op == "add":
            return lhs + rhs
        if op == "sub":
            return lhs - rhs
        if op == "mul":
            return lhs * rhs
        return lhs / rhs
    except pint.DimensionalityError as exc:
        # This is the guardrail doing its job, not a bug. Adding kg P to
        # labour-hours is forbidden by D-002 and the units layer enforces it.
        raise ExpressionError(f"dimensional error in {op!r}: {exc}") from exc


def _bracket_sum(
    node: BracketSum,
    over: str,
    bind: str,
    body: Node,
    agent: AttributeSource,
    bindings: dict[str, pint.Quantity],
    standards: dict[str, Any] | None,
    stack: tuple[str, ...],
) -> Value:
    """Sum ``body`` over each entry of the attribute table ``over``.

    Bracket tables are flat attributes sharing a prefix: an agent with
    ``population.age.0_4``, ``population.age.5_14`` and so on exposes the
    table ``population.age``. Iteration is over sorted keys, because
    determinism forbids order-dependent floating-point accumulation.
    """
    prefix = f"{over}."
    keys = sorted(key for key, _ in getattr(agent, "attributes", ()) if key.startswith(prefix))
    if not keys:
        raise ExpressionError(f"no bracket table {over!r} on this agent")

    total: pint.Quantity | None = None
    for key in keys:
        bracket_bindings = dict(bindings)
        bracket_bindings[bind] = ureg.Quantity(agent.attribute(key), "dimensionless")
        term = evaluate(body, agent, bindings=bracket_bindings, standards=standards, _stack=stack)
        if isinstance(term, bool):
            raise ExpressionError("bracket_sum body must be a quantity, not a boolean")
        total = term if total is None else total + term

    assert total is not None  # keys is non-empty
    return total


def evaluate_quantity(
    node: Node,
    agent: AttributeSource,
    *,
    standards: dict[str, Any] | None = None,
) -> pint.Quantity:
    """Evaluate an expression that must produce a quantity, not a boolean.

    Comparisons are only meaningful inside an ``if`` condition; an expression
    that yields a bare boolean where a requirement was expected is a mistake
    worth catching at the boundary.
    """
    result = evaluate(node, agent, standards=standards)
    if isinstance(result, bool):
        raise ExpressionError("expression evaluated to a boolean, not a quantity")
    return result
