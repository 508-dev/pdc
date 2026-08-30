"""Valueflows actions and their resource effects.

Adopted from Valueflows v1.0.0 unchanged. We do not invent an event taxonomy;
VF's is well thought through and using it keeps PDC data exportable to any
other VF system. See docs/ontology.md section 1.3.

VF carries machine-readable behaviour flags on each action so that resource
updates are data-driven rather than a switch statement. That table is
reproduced here.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class Action(enum.Enum):
    """The Valueflows action vocabulary.

    Only the subset PDC v1 exercises is listed. The remainder (accept, modify,
    pickup, dropoff, combine, separate, deliverService, copy) are part of VF
    and will be added when transport and repair are modelled.
    """

    PRODUCE = "produce"
    """A resource is created, or a stock of the same kind incremented."""

    CONSUME = "consume"
    """An input is transformed into outputs or used up. Gone afterwards."""

    USE = "use"
    """Equipment used but not consumed. Unavailable during the process."""

    WORK = "work"
    """Labour applied to a process.

    No resource is involved — only the provider agent and a skill
    specification. This is VF's treatment and it is the correct one: labour is
    not a substance that moves around a warehouse.
    """

    CITE = "cite"
    """An input neither used nor consumed: a design, a technique, a paper."""

    RAISE = "raise"
    """Adjust a quantity up: opening balances, or a physical count that found
    more than the records showed. Prefer the real action when it is known."""

    LOWER = "lower"
    """Adjust a quantity down. Same caveat."""

    TRANSFER = "transfer"
    """Rights and custody both move to another agent."""

    TRANSFER_CUSTODY = "transferCustody"
    """Physical custody moves; rights do not. Loans, transport, repair."""

    TRANSFER_ALL_RIGHTS = "transferAllRights"
    """Rights move; physical custody does not."""

    MOVE = "move"
    """Location changes. No change of agent."""


class Effect(enum.Enum):
    """How an action affects the quantity of an inventoried resource."""

    INCREMENT = "increment"
    DECREMENT = "decrement"
    DECREMENT_INCREMENT = "decrementIncrement"
    """Decrement the source resource, increment the destination."""
    NONE = "none"


class IO(enum.Enum):
    """Whether a flow with this action is an input to a process, an output,
    or must not be attached to one."""

    INPUT = "input"
    OUTPUT = "output"
    NOT_APPLICABLE = "notApplicable"


@dataclass(frozen=True, slots=True)
class ActionBehaviour:
    """VF's data-driven behaviour flags for one action."""

    io: IO
    onhand_effect: Effect
    accounting_effect: Effect
    creates_resource: bool = False
    is_effort: bool = False
    """True when the quantity is an effort (labour-hours) rather than a
    resource quantity. `work` always; `use` may carry both."""


BEHAVIOUR: dict[Action, ActionBehaviour] = {
    Action.PRODUCE: ActionBehaviour(
        IO.OUTPUT, Effect.INCREMENT, Effect.INCREMENT, creates_resource=True
    ),
    Action.CONSUME: ActionBehaviour(IO.INPUT, Effect.DECREMENT, Effect.DECREMENT),
    Action.USE: ActionBehaviour(IO.INPUT, Effect.NONE, Effect.NONE, is_effort=True),
    Action.WORK: ActionBehaviour(IO.INPUT, Effect.NONE, Effect.NONE, is_effort=True),
    Action.CITE: ActionBehaviour(IO.INPUT, Effect.NONE, Effect.NONE),
    Action.RAISE: ActionBehaviour(
        IO.NOT_APPLICABLE, Effect.INCREMENT, Effect.INCREMENT, creates_resource=True
    ),
    Action.LOWER: ActionBehaviour(IO.NOT_APPLICABLE, Effect.DECREMENT, Effect.DECREMENT),
    Action.TRANSFER: ActionBehaviour(
        IO.NOT_APPLICABLE, Effect.DECREMENT_INCREMENT, Effect.DECREMENT_INCREMENT
    ),
    Action.TRANSFER_CUSTODY: ActionBehaviour(
        IO.NOT_APPLICABLE, Effect.DECREMENT_INCREMENT, Effect.NONE
    ),
    Action.TRANSFER_ALL_RIGHTS: ActionBehaviour(
        IO.NOT_APPLICABLE, Effect.NONE, Effect.DECREMENT_INCREMENT
    ),
    Action.MOVE: ActionBehaviour(IO.NOT_APPLICABLE, Effect.NONE, Effect.NONE),
}
