# Ontology

PDC's data model is [Valueflows v1.0.0](https://www.valueflo.ws/) with one
algorithm replaced and three concepts added. This document states the mapping
precisely, so that PDC data is exportable to any other Valueflows system and
so that the places we diverge are explicit rather than accidental.

Valueflows is CC-BY-SA 4.0. The specification's system of record is the
[Turtle file](https://codeberg.org/valueflows/pages/src/branch/main/assets/all_vf.TTL);
the repository lives on [Codeberg](https://codeberg.org/valueflows/valueflows)
(the GitHub mirror is a tombstone).

---

## 1. What we take unchanged

### 1.1 Agents, resources, processes

| VF class | Use in PDC |
| --- | --- |
| `Agent` (`Person`, `Organization`) | People, households, farms, workshops, communes, valleys, regions. Also **ecosystems** — a soil body, an aquifer, a watershed. VF explicitly sanctions this. |
| `AgentRelationship` | Recursive nesting (D-009). A household `memberOf` a commune `memberOf` a valley. Every aggregate query walks this. |
| `ResourceSpecification` | The *kind* of a thing: wheat grain, elemental phosphorus, nursing hours, alfalfa dry matter. |
| `EconomicResource` | An actual accountable quantity somewhere: 4,200 kg wheat at Northsetting Store, harvested 2027-08. |
| `ProcessSpecification` | The *kind* of a transformation: milling, sowing, lactation. Also serves as resource `stage`. |
| `Process` | An actual scheduled or observed transformation with inputs and outputs. |

### 1.2 The flow progression

This is the spine, and it is why VF is worth adopting rather than reinventing:

```
RecipeFlow  ──►  Intent  ──►  Commitment  ──►  EconomicEvent
 (defined)     (potential)    (agreed)         (observed)
```

- **`Intent`** — a potential future event nobody has agreed to. Offers and
  requests. In PDC, need standards *generate* Intents (§3.1).
- **`Commitment`** — a potential future event the involved agents have agreed
  to pursue. `Commitment.satisfies → Intent`.
- **`EconomicEvent`** — **an observed past flow, never a future one.**
  `EconomicEvent.fulfills → Commitment`.

**Predicted-versus-actual is native.** The divergence Caleb wanted as a
first-class queryable object already is one:

```
divergence(commitment) = Σ quantity(events fulfilling it) − commitment.quantity
```

We do not design this. We query it. The one thing we add is that divergence is
*materialised and trended*, because the point is not to catch a single missed
delivery — it is to learn that a farm's stated yield coefficient has been
optimistic by 12% for four years running, and to feed that back into the model
(§4).

VF also notes a legitimate grey area: when making an operational plan where no
agent needs to be recruited, `Commitment` may be used directly without a prior
`Intent`. The criterion is firmness of plan, not whether an agent has signed.

### 1.3 Actions

We adopt VF's action vocabulary wholesale rather than inventing an event
taxonomy. The ones that matter for v1:

| Action | Meaning | v1 |
| --- | --- | --- |
| `produce` | A resource is created or a stock incremented. | ✓ |
| `consume` | An input is transformed or used up; it is gone afterwards. | ✓ |
| `use` | Equipment used but not consumed; unavailable during the process. | ✓ |
| `work` | **Labour applied to a process. No resource is involved** — only the provider agent and a skill `ResourceSpecification`. | ✓ |
| `cite` | An input neither used nor consumed — a design, a paper, a technique. | ✓ |
| `raise` / `lower` | Adjustments from a real-world count, or opening balances. | ✓ |
| `transfer`, `transferCustody`, `transferAllRights` | Rights and/or custody move between agents. | ✓ |
| `move` | Location changes, no change of agent. | ✓ |
| `accept` / `modify` | Repair, testing, modification — same resource in and out. | later |
| `pickup` / `dropoff` | Transport. | v2 (transport module) |
| `combine` / `separate` | Packing, herds, kits. | later |
| `deliverService` | Intangible output delivered as it is created. | later |
| `copy` | Digital duplication. | later |

`work` deserves emphasis: labour in VF is not a resource that gets moved
around. It is an action with a provider agent and an effort quantity, typed by
a skill specification. That is exactly the treatment labour should have here,
and it is one of several places VF turns out to be better thought through than
a first-principles design would have been.

VF actions carry machine-readable behaviour flags — `accountingEffect`,
`onhandEffect`, `locationEffect`, `stageEffect`, `containedEffect`,
`accountableEffect` — so resource updates are data-driven rather than a switch
statement. PDC implements them as a table.

### 1.4 Recipes and the three-layer model

VF separates:

1. **Recipe layer** — `RecipeProcess`, `RecipeFlow`, `RecipeResource`. Generic,
   reusable definitions of how a thing is made. Batch-sized at the lowest
   natural quantity, scaled when planning.
2. **Plan layer** — `Plan`, `Process`, `Commitment`, `Intent`. A specific
   scheduled body of work.
3. **Observation layer** — `EconomicEvent`, `EconomicResource`. What happened.

PDC uses all three. Recipes are where coefficients live — kg P per tonne of
grain, labour-hours per hectare, water per hectare — and therefore where
public auditability bites hardest (§3.3).

### 1.5 Ecological accounting

VF's ecology guidance is directly usable and we adopt its framing:

- Ecosystems can be **agents**. A soil body receives phosphorus and provides
  nutrient availability. An aquifer provides water and receives recharge.
- "Bad" resources are just resources. Emissions, runoff, silica dust, and
  depletion are `EconomicResource`s with the same machinery as grain. VF's
  point that good/bad is conditional — CO₂ is good in a greenhouse and bad in
  the atmosphere, and it is the same substance — is correct and we do not
  encode a valence.

Phosphorus drawdown in PDC is therefore not a special case. It is a soil agent
whose stock decrements, modelled with the same primitives as a granary.

### 1.6 Algorithms we take

- **`dependent-demand`** — MRP-style backward explosion through the recipe
  graph with backscheduling. Adopted for the demand-driven direction (§2.2).
- **`track` / `trace` / `provenance`** — forward and backward flow traversal.
  Adopted; these are how "where did this bread's phosphorus come from" is
  answered. Note VF's guidance on breadcrumbing when the graph has cycles
  (repeated process specifications), which agriculture certainly does.

---

## 2. What we replace

### 2.1 Value rollup → dimensional rollup

**This is the divergence.** VF's `rollup` algorithm says, verbatim:

> "all of the input values need to be converted into the same unit: often, but
> not necessarily, a unit of money... In a time bank system, the unit would be
> hours."

VF is agnostic about *which* scalar. It is not agnostic about there being one.
That is the reduction D-002 forbids.

PDC's replacement propagates a **`CostVector`**: a mapping from
`ResourceSpecification` to `Quantity` that supports addition and scaling but
has no defined operation that produces a scalar. The cost of a loaf is:

```
{ labour.field_hours: 0.011 h
, labour.mill_hours:  0.002 h
, labour.bake_hours:  0.008 h
, soil.P:             1.9 g
, water.irrigation:   340 L
, land.ha_season:     2.4e-5 ha·a
, energy.process:     0.9 MJ }
```

...and it stays that shape forever. There is no `.total()`. Rendering a cost
vector as a single number is not a feature we omitted; it is a feature we
refuse.

### 2.2 Joint products: attribution is explicit, never defaulted

A dairy produces milk *and* manure. A wheat field produces grain *and* straw.
The phosphorus entering the process has to be attributed across outputs, and
**every possible allocation rule is a value judgement**.

PDC does not pick one. An attribution rule is a **named object attached to the
process**, and every cost-vector query returns the rule it used:

> "this bread carries 1.9 g P **under attribution rule `mass-proportional`**"

Swapping to `energy-proportional` or `grain-only` or a hand-specified split is
a visible operation with a visible effect on every downstream number. The
alternative — silently defaulting to allocation by mass — is D-002's failure
mode hidden one layer down where nobody audits it. Joint costs may also be
carried *unattributed*, as a set jointly charged to all outputs, which is the
honest representation when no rule is agreed.

---

## 3. What we add

Three concepts Valueflows does not have.

### 3.1 `NeedStandard`

VF's `Intent` is a declared request. PDC needs requirement *derived* from
population and a cited standard whether or not anyone asked.

```
NeedStandard
  id                  stable identifier, e.g. sphere-2018:food-energy
  name                human-readable
  author              Agent who published it
  citation            REQUIRED — source document, DOI, URL, or deliberation record
  version             semver; standards are immutable once published
  applies_to          predicate over agent attributes (who is this for?)
  requires            declared attribute dependencies, validated up front
  expression          the calculation (§3.2)
  produces            ResourceSpecification and unit of the result
```

Evaluating a standard against an agent yields a requirement quantity, which
becomes a VF `Intent` — so downstream, need flows through the same machinery
as any other demand and remains exportable to any VF system.

Three properties, from D-006:

- **No ordering, no privileged set.** `sphere-2018:survival`,
  `usda-dri:adult-female-31-50`, and `northsetting:comfortable-2027` are peers.
  Tiers are several standards someone chose to publish in an order.
- **A missing citation is a validation error**, not a warning.
- **A missing required attribute is a loud failure**, never a silent zero.
  Silent zeros in a needs calculation are the worst available failure mode.

Agent attributes are a small fixed core — population, age-sex structure,
location, climate normals — plus an open namespaced extension map.

### 3.2 The standard expression language

Total, pure, deterministic, unit-aware, serialized as a JSON AST. Per D-007,
the design constraint is that a second implementation must be cheap.

Node set:

| Node | Form | Notes |
| --- | --- | --- |
| `lit` | `{value, unit}` | Unit-tagged literal. |
| `attr` | `{path}` | Reads an agent attribute. Missing → error. |
| `add` `sub` `mul` `div` | binary | Dimensional checking applies. |
| `min` `max` | n-ary | |
| `clamp` | `{value, lo, hi}` | |
| `if` | `{cond, then, else}` | Both branches evaluated for type; one returned. |
| `lt` `lte` `gt` `gte` `eq` | binary | Returns boolean. |
| `bracket_sum` | `{over, bind, body}` | **Bounded** summation over a declared attribute table — e.g. population by age-sex bracket. Iterates over data of known finite size. |
| `ref` | `{standard_id}` | References another standard's result. Forms a DAG; cycles rejected at validation. |

There is no `while`, no `lambda`, no user-defined function, no I/O, no
recursion. Every expression terminates. The evaluator is intended to be small
enough — low hundreds of lines — that reimplementing it is a weekend, not a
project.

A worked example, "2,300 kcal per person per day, plus a temperature term for
water":

```json
{"op": "mul",
 "left":  {"op": "attr", "path": "population"},
 "right": {"op": "lit", "value": 2300, "unit": "kcal/day"}}
```

### 3.3 `ResponseModel`

Separate object type, per D-008, because it makes a different *kind* of claim:
what happens to people when need is unmet.

```
ResponseModel
  id, name, author, citation, version
  domain            which need standard's shortfall it responds to
  expression        shortfall → consequence
  affects           what it modifies: labour capacity, population, morbidity
```

**Off by default.** Default behaviour on unmet need is to report the shortfall
in physical units and stop. Simulation and game contexts opt in by name; a live
deployment should have to choose it deliberately and know it has.

Mortality and other absorbing states belong to the **population model**, not
here and not in `NeedStandard` — which keeps `NeedStandard` a pure function of
current attributes and keeps the politically loaded dynamics in one clearly
labelled place.

---

## 4. Model refinement from observation

Coefficients are beliefs, and the observation layer is how they are corrected.

A recipe coefficient (kg P per tonne grain, labour-hours per hectare) carries
provenance: who asserted it, from what source, and its observed history. As
`EconomicEvent`s accumulate against `Commitment`s derived from that
coefficient, the system materialises the divergence and its trend.

It does **not** auto-update the coefficient. It surfaces the discrepancy —
"this recipe has over-predicted yield by 9–14% for four seasons" — and a human
revises the recipe, publicly, as a new version. Automatic fitting would put
the model beyond the reach of the hand-verification that D-007 exists to
protect.

---

## 5. Deliberately absent

| Not modelled | Why |
| --- | --- |
| Money, credits, prices, labour-time accounting | D-002. No universal equivalent. |
| Votes, quorum, blocking, delegation | D-011. Consensus mechanics are out of scope. |
| VF `Exchange`, `Proposal` reciprocity, `Claim`, `Settlement` | These model reciprocal obligation — the barter/exchange half of VF. Not used. Retained in the export mapping only so PDC data remains readable by other VF systems. |
| Priority scores, urgency weights, vulnerability multipliers | Each is a scalar smuggled in through the back door. Shortfalls are reported per-standard, per-resource, per-agent, unranked. |
| An objective function | D-001, D-004. |
