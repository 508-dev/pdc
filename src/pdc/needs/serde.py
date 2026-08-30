"""JSON serialisation for the expression language.

The wire format is the specification. A standard is published as this JSON,
and anyone reimplementing the evaluator implements against this and nothing
else. Keep it boring and explicit — no shorthand, no inference, no version
negotiation cleverness.
"""

from __future__ import annotations

from typing import Any

from pdc.needs.expr import (
    Attr,
    BinOp,
    BracketSum,
    Clamp,
    ExpressionError,
    If,
    Lit,
    NAry,
    Node,
    Ref,
)


def to_json(node: Node) -> dict[str, Any]:
    """Serialise an expression to its canonical JSON form."""
    match node:
        case Lit(value, unit):
            return {"op": "lit", "value": value, "unit": unit}
        case Attr(path, unit):
            return {"op": "attr", "path": path, "unit": unit}
        case BinOp(op, left, right):
            return {"op": op, "left": to_json(left), "right": to_json(right)}
        case NAry(op, operands):
            return {"op": op, "operands": [to_json(o) for o in operands]}
        case Clamp(value, lo, hi):
            return {"op": "clamp", "value": to_json(value), "lo": to_json(lo), "hi": to_json(hi)}
        case If(cond, then, otherwise):
            return {
                "op": "if",
                "cond": to_json(cond),
                "then": to_json(then),
                "else": to_json(otherwise),
            }
        case BracketSum(over, bind, body):
            return {"op": "bracket_sum", "over": over, "bind": bind, "body": to_json(body)}
        case Ref(standard_id):
            return {"op": "ref", "standard_id": standard_id}
    raise ExpressionError(f"cannot serialise {type(node).__name__}")


def from_json(data: dict[str, Any]) -> Node:
    """Parse an expression from its canonical JSON form."""
    if not isinstance(data, dict) or "op" not in data:
        raise ExpressionError(f"expression node must be an object with an 'op': {data!r}")

    op = data["op"]
    match op:
        case "lit":
            return Lit(float(data["value"]), str(data["unit"]))
        case "attr":
            return Attr(str(data["path"]), str(data.get("unit", "dimensionless")))
        case "add" | "sub" | "mul" | "div" | "lt" | "lte" | "gt" | "gte" | "eq":
            return BinOp(op, from_json(data["left"]), from_json(data["right"]))
        case "min" | "max":
            return NAry(op, tuple(from_json(o) for o in data["operands"]))
        case "clamp":
            return Clamp(from_json(data["value"]), from_json(data["lo"]), from_json(data["hi"]))
        case "if":
            return If(from_json(data["cond"]), from_json(data["then"]), from_json(data["else"]))
        case "bracket_sum":
            return BracketSum(str(data["over"]), str(data["bind"]), from_json(data["body"]))
        case "ref":
            return Ref(str(data["standard_id"]))
    raise ExpressionError(f"unknown operator {op!r}")
