"""Canonical serialisation and content addressing.

Reproducibility is the auditability mechanism (D-010): someone runs a scenario
against their own mirror and finds out exactly where their model and yours
disagree. That only works if "the same scenario" and "the same result" are
decidable, which means one canonical byte-level form for everything.

Rules, all of them boring on purpose:

- Object keys sorted, no insignificant whitespace.
- Floats via Python's repr, which round-trips exactly.
- Quantities as magnitude plus canonical unit name, never as a formatted
  string, because display formatting is allowed to change and hashes are not.
- No timestamps, no host information, no library versions beyond the kernel's
  own. A digest must not change because someone ran it on a Tuesday.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pint


def quantity_json(quantity: pint.Quantity) -> dict[str, Any]:
    """A quantity as magnitude and canonical unit name."""
    return {"magnitude": float(quantity.magnitude), "units": str(quantity.units)}


def canonical_json(value: Any) -> str:
    """The one serialisation a digest is taken over."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    """SHA-256 over the canonical form, hex encoded.

    Not a signature — this says nothing about who produced the value, only
    that two people are looking at the same one. Signatures are v2 (D-010),
    and the two guarantees are deliberately kept separate.
    """
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def short(value: str, length: int = 12) -> str:
    """A digest abbreviated for display. Never for comparison."""
    return value[:length]
