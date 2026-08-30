# Architecture

How the pieces fit. Decisions are in `DECISIONS.md`; the data model is in
`docs/ontology.md`. This document is about layering, the simulation kernel,
and the propagation engine.

---

## 1. Layering

```
┌─────────────────────────────────────────────────────────────┐
│  Shells        CLI simulator · HTTP API · game backend      │  peripheral
│                (nothing here is imported by the kernel)     │
├─────────────────────────────────────────────────────────────┤
│  Adapters      Postgres persistence · scenario export       │
├─────────────────────────────────────────────────────────────┤
│  Analysis      feasibility · gap analysis · enumeration     │
│                (never optimisation — D-001, D-004)          │
├─────────────────────────────────────────────────────────────┤
│  Simulation    branched worlds · forward propagation ·      │
│                dependent demand · determinism guarantees    │
├─────────────────────────────────────────────────────────────┤
│  Needs         NeedStandard · expression language ·         │
│                ResponseModel (opt-in)                       │
├─────────────────────────────────────────────────────────────┤
│  Costing       dimensional CostVector · attribution rules   │
├─────────────────────────────────────────────────────────────┤
│  Ontology      Valueflows v1.0.0 entities and actions       │
├─────────────────────────────────────────────────────────────┤
│  Units         pint registry · substance-aware types        │
└─────────────────────────────────────────────────────────────┘
```

Dependencies point downward only. The kernel is everything from Units through
Analysis: pure Python, no framework, no database, no clock, no network. It is
importable and fully exercisable with nothing installed but its own
dependencies, which is the property that makes determinism testable.

---

## 2. The units layer

Everything above this line is dimensioned. `pint` provides the registry;
serialization uses om2 (Ontology of units of Measure) URIs, matching
Valueflows.

The non-obvious part is **substance-aware typing** (D-013). These are distinct
dimensions that refuse to add:

| Convention A | Convention B | Factor | Where it bites |
| --- | --- | --- | --- |
| kg P (elemental) | kg P₂O₅ | ×2.29 | Fertiliser labels vs. soil science |
| kg K (elemental) | kg K₂O | ×1.20 | Same |
| kg N | kg crude protein | ×6.25 | Feed and nutrition tables |
| kg fresh weight | kg dry matter | crop-specific | Forage, silage, almost all feed |

A model that mixes P and P₂O₅ overstates phosphorus by 2.29× and every
downstream number still looks plausible. Conversions exist and are explicit
and named; implicit coercion raises.

Dry matter deserves particular care: forage yields are quoted both ways, the
ratio varies from ~20% (fresh silage) to ~90% (hay), and getting it wrong
silently changes a livestock model by a factor of four.

---

## 3. The simulation kernel

### 3.1 Worlds and branches

A **`World`** is the complete state at a point in time: agents, resources,
recipes, standards, and the event log that produced it.

A **`Branch`** is a world derived from a parent by an ordered set of
assumptions. Reality is the branch whose events are human-authored (D-005);
it has no special type.

Storage is **deltas from parent, immutable and content-addressed**. Scenario
exploration spawns branches in the thousands and copying a world per branch
dies quickly. A branch is:

```
Branch
  parent            content hash of parent branch (None for root)
  assumptions       ordered, immutable list of deltas
  hash              content hash over (parent, assumptions)
```

Identical assumptions applied to an identical parent produce an identical
hash. That is what makes "run this scenario against your own mirror" a
verifiable claim rather than a hopeful one.

### 3.2 Determinism

Non-negotiable, because reproducibility is the auditability mechanism (D-010).

Prohibited anywhere in the kernel:

- Wall-clock reads. Simulation time is explicit and passed in.
- Unseeded randomness. Every stochastic process takes an explicit seed derived
  from the branch hash.
- Iteration over unordered collections where order affects results. Sets and
  dicts are sorted at every boundary that feeds computation.
- Floating-point accumulation in nondeterministic order. Reductions run over
  sorted keys.
- Any I/O, network access, or environment read.

Enforcement is a test that runs the reference scenario twice in one process
and once in a subprocess with a different `PYTHONHASHSEED`, and asserts
byte-identical serialized results.

### 3.3 Scenario export

A scenario serializes to a self-contained file: `(parent world identity,
ordered assumptions, results, kernel version, coefficient set hash)`. Handing
someone that file lets them reproduce it exactly, or reproduce it against
their own coefficients and see precisely where the two of you disagree.

This is the artefact people argue over. It is the primary output of v1, and
the reason v1 has no UI: the data is the deliverable.

---

## 4. Propagation

Two engines over the same recipe graph, in opposite directions.

### 4.1 Forward, supply-driven (v1)

Given the resources actually on hand and an allocation, what happens
downstream, over multiple periods, with lags. This is the engine the
motivating question needs:

> *If we direct all the phosphorus to farm A, farm B will not produce the
> alfalfa that ranches C and D need the year after, which costs the system 50%
> of its calories. If we split the phosphorus, the loss is 15%.*

Valueflows notes that manufacturing is usually demand-driven while
**agriculture is usually supply-driven**, which is why this direction comes
first.

Per period `t`, per process:

1. **Determine the limiting input.** Output is bounded by
   `min over inputs i of (available_i / coefficient_i) × nominal_output`.
   This is Liebig's law of the minimum, which is both agronomically correct and
   exactly the gap analysis D-004 calls for: *the binding constraint is the
   answer*, named and quantified in its own units, rather than a score.
2. **Emit flows.** `consume` the inputs actually drawn, `work` the labour,
   `use` the equipment, `produce` the output.
3. **Apply lags.** Output becomes available at `t + lag`. Alfalfa sown this
   season feeds cattle next season; a soil phosphorus deficit shows up in the
   yield of the season after the one in which it was created. Lags are recipe
   properties, and they are the reason a single-period model cannot answer the
   motivating question.
4. **Decrement stocks**, including ecosystem agents. Soil phosphorus is a
   stock with a balance like any other.

Then per period, per agent: evaluate declared need standards, compare against
available resources, emit a shortfall vector. If a `ResponseModel` is
explicitly enabled, apply it; otherwise stop at the shortfall.

Output of a forward run is a **vector of physical outcomes per agent per
period** — not a score. Aggregating kcal across the region to say "15% calorie
loss" is legitimate under D-002 because it is arithmetic within one unit.

### 4.2 Backward, demand-driven (v2)

Valueflows' `dependent-demand` algorithm, adopted as specified: traverse the
recipe graph backwards from a required output, matching recipe inputs to
recipe outputs by resource specification, allocating existing stock and
scheduled outputs to the earliest demand first, and backscheduling processes
by their durations. Where no recipe can produce a needed input, report the
gap rather than suggesting a purchase.

Same graph, same coefficients, opposite direction.

---

## 5. Analysis

Three operations, per D-004. None of them rank.

- **`feasible(world, standards) -> bool + witness`** — is there any allocation
  meeting these standards? If yes, one witness allocation. If no, the
  infeasibility certificate: which constraints conflict.
- **`gaps(world, standards) -> ShortfallVector`** — per agent, per resource,
  in native units, with the binding constraint named.
- **`frontier(world, options) -> [Outcome]`** — the non-dominated set over
  options, unranked and unordered. Dominance is defined per-dimension: an
  option dominates another only if it is at least as good in *every* dimension
  and better in one. Most pairs of options are incomparable, and that is the
  correct answer rather than a limitation to be engineered around.

Shadow prices are available behind an explicit call that returns them tagged
with the constraint set and instant that produced them. They are never stored.

---

## 6. Persistence

Postgres, as an adapter. The kernel does not import it.

Two properties from D-010, present in the first migration:

- Every event row carries `author_agent`, `signature`, and `prev_hash`,
  nullable and unenforced until v2. Retrofitting a hash chain requires
  rewriting history — the exact thing a chain exists to prevent.
- The log is append-only. Corrections are new events (VF's `raise` / `lower`),
  never mutations.

The database is intended to be dumped, mirrored, and recomputed by anyone. It
holds no secrets by design.

---

## 7. Repository layout

```
src/pdc/
  units/          registry, substance types, conversions
  ontology/       agents, resources, processes, recipes, flows, actions
  costing/        CostVector, attribution rules
  needs/          NeedStandard, expression language, ResponseModel
  sim/            World, Branch, forward propagation, determinism guards
  analysis/       feasibility, gaps, frontier
  seed/           synthetic reference region generator + coefficient tables
  cli/            the simulator shell
tests/
docs/
```

`adapters/` (Postgres) and further shells arrive when there is something to
persist or serve. Nothing under `sim/`, `needs/`, `costing/`, `ontology/`, or
`units/` may import from `adapters/` or `cli/`; a test enforces this.

---

## 8. Deferred, with the reason

| Deferred | Until | Why not now |
| --- | --- | --- |
| Web UI | after v1 | A UI over a wrong kernel makes wrong answers persuasive. |
| Signatures, key management | v2 | Schema is ready (§6). Building key management before a working simulation is how the project dies at month three. |
| Cross-instance federation | v2+ | The recursive agent tree (D-009) makes this aggregation at a different depth, not a new subsystem. |
| Transport and energy modules | v2+ | Ontology supports them as recipes today. Energy should integrate PyPSA or Calliope rather than reimplement them. |
| Solver (HiGHS / OR-Tools) | when enumeration needs it | Forward propagation answers the motivating question without one. |
| Manufacturing, raw-material extraction | v3+ | Same primitives, more coefficient data. |
