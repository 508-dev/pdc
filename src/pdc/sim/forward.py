"""Forward, supply-driven propagation.

Given what is actually on hand and how it has been allocated, what happens
downstream, over several periods, with lags. This is the engine the reference
question needs:

    If we direct all the phosphorus to one farm, the alfalfa crop fails, and
    the ranches that depend on it are short the year after.

Valueflows notes that manufacturing is usually demand-driven while agriculture
is usually supply-driven, which is why this direction comes first.

Output is not a score. It is a set of physical outcomes per agent per period,
plus a Cause tree explaining each shortfall down to the coefficient and
citation that produced it (D-001, D-004).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import pint

from pdc.costing.rollup import COSTED_ACTIONS
from pdc.needs import NeedStandard
from pdc.ontology import Action, Agent, RecipeProcess, ResourceComposition
from pdc.sim.explain import Cause, CauseKind, Evidence
from pdc.sim.world import Allocation, ProcessPlan, Scenario, StockKey, WorldState
from pdc.units import negated, ureg


@dataclass(frozen=True, slots=True)
class ProcessOutcome:
    """What a planned process actually managed."""

    agent_id: str
    recipe_id: str
    period: int
    intended_batches: float
    achieved_batches: float
    binding_specification_id: str | None
    cause: Cause | None
    """Populated when the process ran below intention."""

    @property
    def underran(self) -> bool:
        return self.achieved_batches < self.intended_batches - 1e-9

    @property
    def shortfall_fraction(self) -> float:
        if self.intended_batches <= 0:
            return 0.0
        return 1.0 - (self.achieved_batches / self.intended_batches)


@dataclass(frozen=True, slots=True)
class NeedOutcome:
    """A community measured against one standard, in one period."""

    agent_id: str
    standard_id: str
    period: int
    required: pint.Quantity
    available: pint.Quantity
    cause: Cause

    @property
    def met(self) -> bool:
        return bool(self.available >= self.required)

    @property
    def shortfall(self) -> pint.Quantity:
        deficit = self.required - self.available
        return deficit if deficit.magnitude > 0 else self.required * 0.0


@dataclass(frozen=True, slots=True)
class PeriodResult:
    period: int
    state: WorldState
    processes: tuple[ProcessOutcome, ...] = ()
    needs: tuple[NeedOutcome, ...] = ()


@dataclass(frozen=True, slots=True)
class ForwardRun:
    """The result of running a scenario forward.

    Deliberately holds no summary number. Reducing "what happened to this
    valley over three years" to one figure would require exchange rates
    between calories, phosphorus, and labour (D-002).
    """

    scenario_label: str
    periods: tuple[PeriodResult, ...] = ()
    assumptions: tuple[str, ...] = field(default_factory=tuple)

    def period(self, index: int) -> PeriodResult:
        return self.periods[index]

    def needs_for(self, agent_id: str, standard_id: str) -> tuple[NeedOutcome, ...]:
        return tuple(
            outcome
            for result in self.periods
            for outcome in result.needs
            if outcome.agent_id == agent_id and outcome.standard_id == standard_id
        )

    def energy_by_period(self, agent_id: str, standard_id: str) -> tuple[pint.Quantity, ...]:
        return tuple(o.available for o in self.needs_for(agent_id, standard_id))


def run_forward(
    scenario: Scenario,
    *,
    agents: Sequence[Agent],
    recipes: Sequence[RecipeProcess],
    standards: Sequence[NeedStandard],
    compositions: Sequence[ResourceComposition],
    opening: WorldState,
    period_days: float = 365.0,
) -> ForwardRun:
    """Run a scenario forward and explain the outcome."""
    recipe_index = {recipe.id: recipe for recipe in sorted(recipes, key=lambda r: r.id)}
    agent_index = {agent.id: agent for agent in sorted(agents, key=lambda a: a.id)}
    composition_index = {c.specification_id: c for c in compositions}

    state = opening
    pending: dict[int, list[tuple[StockKey, pint.Quantity]]] = {}
    results: list[PeriodResult] = []
    history: list[tuple[ProcessOutcome, ...]] = []

    for period in range(scenario.periods):
        state = WorldState(period=period, stocks=state.stocks)

        # Deliver anything whose lag has elapsed.
        for key, quantity in sorted(pending.pop(period, []), key=lambda item: item[0]):
            state = state.adjusted(key, quantity)

        state, outcomes = _run_processes(
            scenario, period, state, pending, recipe_index, agent_index
        )
        history.append(outcomes)

        needs = _evaluate_needs(
            period, state, agent_index, standards, composition_index, history, period_days
        )
        results.append(PeriodResult(period, state, outcomes, needs))

        # People eat. Without this, stocks accumulate forever and every
        # scenario looks like a success by its third period.
        if scenario.consumption_standard_id is not None:
            state = _consume_food(state, needs, scenario.consumption_standard_id, composition_index)

    return ForwardRun(
        scenario_label=scenario.label,
        periods=tuple(results),
        assumptions=(
            f"allocation: {scenario.allocation.label}",
            (
                f"consumption governed by {scenario.consumption_standard_id}"
                if scenario.consumption_standard_id
                else "nothing is consumed; stocks accumulate"
            ),
            "outputs are held by the producing agent's community; cross-community "
            "transfers are not assumed",
            "members of a community draw on that community's pooled stocks",
            f"period length: {period_days:g} days",
        ),
    )


def _draw_limit(
    plan: ProcessPlan,
    flow_specification: str,
    state: WorldState,
    allocation: Allocation,
    agent_index: Mapping[str, Agent],
) -> pint.Quantity | None:
    """What this agent may draw of one input this period.

    An explicit allocation caps the draw absolutely — that is the point of an
    allocation, and it is always a recorded human decision rather than
    something PDC computes (D-001).

    Otherwise the agent draws on its own stock plus its community's pool.
    That pooling is an assumption, stated in every run's assumption list: it
    says members of a commune share what the commune holds. A federation that
    does not work that way models the boundary with an explicit allocation
    instead.
    """
    granted = allocation.granted(plan.agent_id, flow_specification)
    if granted is not None:
        return granted

    total: pint.Quantity | None = None
    for holder in _draw_order(agent_index, plan.agent_id):
        held = state.held(holder, flow_specification)
        if held is None:
            continue
        total = held if total is None else total + held
    return total


def _draw_order(agent_index: Mapping[str, Agent], agent_id: str) -> tuple[str, ...]:
    """Where an agent draws from, nearest first: itself, then its commune."""
    agent = agent_index.get(agent_id)
    if agent is None or agent.member_of is None or agent.kind in ("commune", "region"):
        return (agent_id,)
    return (agent_id, agent.member_of)


def _consume(
    state: WorldState,
    agent_index: Mapping[str, Agent],
    agent_id: str,
    specification_id: str,
    quantity: pint.Quantity,
) -> WorldState:
    """Draw a quantity, taking from the agent's own stock before the pool."""
    remaining = quantity
    for holder in _draw_order(agent_index, agent_id):
        if remaining.magnitude <= 0:
            break
        held = state.held(holder, specification_id)
        if held is None or held.magnitude <= 0:
            continue
        taken = held if held < remaining else remaining
        state = state.adjusted((holder, specification_id), negated(taken))
        remaining = remaining - taken

    if remaining.magnitude > 1e-9:
        # Liebig should have prevented this. Recording it rather than
        # swallowing it, because a negative stock is a modelling bug and
        # silently allowing one would corrupt every later period.
        state = state.adjusted((agent_id, specification_id), negated(remaining))
    return state


def _run_processes(
    scenario: Scenario,
    period: int,
    state: WorldState,
    pending: dict[int, list[tuple[StockKey, pint.Quantity]]],
    recipe_index: Mapping[str, RecipeProcess],
    agent_index: Mapping[str, Agent],
) -> tuple[WorldState, tuple[ProcessOutcome, ...]]:
    outcomes: list[ProcessOutcome] = []

    for plan in scenario.plans_for(period):
        recipe = recipe_index[plan.recipe_id]

        # Liebig's law of the minimum: output is bounded by whichever input
        # runs out first. This is both agronomically correct and exactly the
        # gap analysis D-004 asks for — the binding constraint is the answer,
        # named and quantified in its own units, rather than a score.
        limits: list[tuple[str, float, pint.Quantity, pint.Quantity]] = []
        for flow in recipe.inputs:
            if flow.action not in COSTED_ACTIONS:
                continue
            if flow.action is Action.WORK:
                # Labour is not modelled as a constrained stock in v1. It is
                # recorded on the flows and rolled up, but a labour ceiling
                # needs a workforce model, which is not yet built.
                continue

            available = _draw_limit(
                plan, flow.specification_id, state, scenario.allocation, agent_index
            )
            if available is None:
                available = flow.quantity * 0.0
            ratio = (available / flow.quantity).to("dimensionless").magnitude
            limits.append((flow.specification_id, ratio, available, flow.quantity))

        achievable = plan.intended_batches
        binding: tuple[str, float, pint.Quantity, pint.Quantity] | None = None
        for limit in sorted(limits, key=lambda item: (item[1], item[0])):
            if limit[1] < achievable:
                achievable = limit[1]
                binding = limit
                break

        achievable = max(achievable, 0.0)

        cause = None
        if binding is not None and achievable < plan.intended_batches - 1e-9:
            specification, _, available, per_batch = binding
            required = per_batch * plan.intended_batches
            cause = Cause(
                kind=CauseKind.PROCESS_UNDERRUN,
                subject_id=plan.agent_id,
                period=period,
                summary=(
                    f"period {period}: {_name(agent_index, plan.agent_id)} ran "
                    f"{recipe.name} at {achievable:,.0f} of "
                    f"{plan.intended_batches:,.0f} intended batches"
                ),
                detail=(
                    ("intended", ureg.Quantity(plan.intended_batches, "dimensionless")),
                    ("achieved", ureg.Quantity(achievable, "dimensionless")),
                ),
                causes=(
                    Cause(
                        kind=CauseKind.BINDING_CONSTRAINT,
                        subject_id=specification,
                        period=period,
                        summary=(
                            f"{specification} was the limiting factor in period "
                            f"{period}: {available:~P} available against "
                            f"{required:~P} required"
                        ),
                        detail=(("available", available), ("required", required)),
                        evidence=(
                            Evidence(
                                description=f"{recipe.id} requires {specification} per batch",
                                quantity=per_batch,
                                citation=next(
                                    f.citation
                                    for f in recipe.inputs
                                    if f.specification_id == specification
                                ),
                            ),
                        ),
                    ),
                ),
            )

        # Apply the flows at the scale actually achieved.
        for flow in recipe.inputs:
            if flow.action is not Action.CONSUME:
                continue
            state = _consume(
                state,
                agent_index,
                plan.agent_id,
                flow.specification_id,
                flow.quantity * achievable,
            )

        holder = _holding_agent(agent_index, plan.agent_id)
        for flow in recipe.outputs:
            if flow.action is not Action.PRODUCE:
                continue
            produced = flow.quantity * achievable
            key = (holder, flow.specification_id)
            if flow.lag_periods > 0:
                pending.setdefault(period + flow.lag_periods, []).append((key, produced))
            else:
                state = state.adjusted(key, produced)

        outcomes.append(
            ProcessOutcome(
                agent_id=plan.agent_id,
                recipe_id=plan.recipe_id,
                period=period,
                intended_batches=plan.intended_batches,
                achieved_batches=achievable,
                binding_specification_id=binding[0] if binding else None,
                cause=cause,
            )
        )

    return state, tuple(outcomes)


def _holding_agent(agent_index: Mapping[str, Agent], agent_id: str) -> str:
    """Where a producing agent's output is held.

    Outputs pool at the producing agent's community. Moving them between
    communities is an allocation decision, and PDC does not make those
    (D-001) — a scenario that assumes a transfer must say so explicitly.
    """
    agent = agent_index.get(agent_id)
    if agent is None or agent.member_of is None or agent.kind in ("commune", "region"):
        return agent_id
    return agent.member_of


def _name(agent_index: Mapping[str, Agent], agent_id: str) -> str:
    agent = agent_index.get(agent_id)
    return agent.name if agent else agent_id


def _evaluate_needs(
    period: int,
    state: WorldState,
    agent_index: Mapping[str, Agent],
    standards: Sequence[NeedStandard],
    composition_index: Mapping[str, ResourceComposition],
    history: Sequence[tuple[ProcessOutcome, ...]],
    period_days: float,
) -> tuple[NeedOutcome, ...]:
    outcomes: list[NeedOutcome] = []

    communes = sorted((a for a in agent_index.values() if a.kind == "commune"), key=lambda a: a.id)

    for agent in communes:
        available, contributions = _available_energy(agent.id, state, composition_index)

        for standard in sorted(standards, key=lambda s: s.id):
            if not all(agent.has_attribute(path) for path in standard.requires):
                continue

            per_day = standard.evaluate(agent)
            required = (per_day * ureg.Quantity(period_days, "day")).to("kcal")

            if available >= required:
                cause = Cause(
                    kind=CauseKind.NEED_SHORTFALL,
                    subject_id=agent.id,
                    period=period,
                    summary=(
                        f"{agent.name} met {standard.id}: {available.to('Mcal'):~P} "
                        f"available against {required.to('Mcal'):~P} required"
                    ),
                    detail=(("available", available), ("required", required)),
                )
            else:
                cause = Cause(
                    kind=CauseKind.NEED_SHORTFALL,
                    subject_id=agent.id,
                    period=period,
                    summary=(
                        f"{agent.name} fell short of {standard.id} by "
                        f"{(required - available).to('Mcal'):~P}"
                    ),
                    detail=(
                        ("required", required),
                        ("available", available),
                        ("shortfall", required - available),
                    ),
                    evidence=(
                        Evidence(
                            description=f"{standard.id} requirement",
                            quantity=per_day,
                            citation=standard.citation,
                        ),
                    ),
                    causes=_explain_energy_shortfall(
                        agent.id, period, contributions, history, agent_index
                    ),
                )

            outcomes.append(NeedOutcome(agent.id, standard.id, period, required, available, cause))

    return tuple(outcomes)


def _available_energy(
    commune_id: str,
    state: WorldState,
    composition_index: Mapping[str, ResourceComposition],
) -> tuple[pint.Quantity, tuple[tuple[str, pint.Quantity], ...]]:
    """Food energy held by a commune.

    Summing kilocalories across several foods is aggregation within one
    dimension, which D-002 permits. Note what is *not* being done: the foods
    are not being scored, ranked, or traded off against each other.
    """
    total = ureg.Quantity(0.0, "kcal")
    contributions: list[tuple[str, pint.Quantity]] = []

    for (holder, specification), quantity in state.stocks:
        if holder != commune_id:
            continue
        composition = composition_index.get(specification)
        if composition is None:
            continue
        energy = (quantity * composition.per_unit).to("kcal")
        if energy.magnitude <= 0:
            continue
        total = total + energy
        contributions.append((specification, energy))

    return total, tuple(sorted(contributions, key=lambda item: item[0]))


def _explain_energy_shortfall(
    commune_id: str,
    period: int,
    contributions: tuple[tuple[str, pint.Quantity], ...],
    history: Sequence[tuple[ProcessOutcome, ...]],
    agent_index: Mapping[str, Agent],
) -> tuple[Cause, ...]:
    """Link a commune's food shortfall to the processes that underran.

    Looks at this period and the one before, because a lagged output means the
    cause of this year's shortage is often last year's failed sowing.
    """
    members = {agent.id for agent in agent_index.values() if agent.member_of == commune_id}

    causes: list[Cause] = []
    seen: set[tuple[str, str, int]] = set()

    for offset in (0, 1):
        index = period - offset
        if index < 0:
            continue
        for outcome in history[index]:
            if outcome.agent_id not in members or outcome.cause is None:
                continue
            key = (outcome.agent_id, outcome.recipe_id, outcome.period)
            if key in seen:
                continue
            seen.add(key)
            causes.append(outcome.cause)

    if contributions:
        causes.append(
            Cause(
                kind=CauseKind.ALLOCATION,
                subject_id=commune_id,
                period=period,
                summary="food energy actually on hand came from",
                detail=contributions,
            )
        )

    return tuple(causes)


def _consume_food(
    state: WorldState,
    needs: Sequence[NeedOutcome],
    consumption_standard_id: str,
    composition_index: Mapping[str, ResourceComposition],
) -> WorldState:
    """Draw down food stocks by what each community actually ate.

    Communities eat up to the named standard, or everything they have if that
    is less. Consumption is spread proportionally across whatever foods are on
    hand, rather than eating one food before another: any priority order would
    be a claim about diet that belongs to the people eating, not to the model.
    """
    for outcome in sorted(needs, key=lambda o: o.agent_id):
        if outcome.standard_id != consumption_standard_id:
            continue

        eaten = outcome.required if outcome.available >= outcome.required else outcome.available
        if eaten.magnitude <= 0 or outcome.available.magnitude <= 0:
            continue

        fraction = (eaten / outcome.available).to("dimensionless").magnitude
        for (holder, specification), quantity in state.stocks:
            if holder != outcome.agent_id or specification not in composition_index:
                continue
            if quantity.magnitude <= 0:
                continue
            state = state.adjusted((holder, specification), negated(quantity * fraction))

    return state
