# Roadmap

Milestones are defined by what becomes *answerable*, not by what gets built.
No dates: this is a long evening project.

---

## v1 — the reference question

**Done when:** the synthetic reference region loads, and PDC answers the
motivating question end to end.

> Allocate all available phosphorus to one farm, or split it. Run forward
> three years with the alfalfa→cattle lag. Report the calorie outcome per
> community per year against each community's declared need standards. Export
> both scenarios; reproduce them byte-identically on a different machine.

### Milestones

**M1 — Units and ontology.**
`pint` registry with substance-aware types that refuse to add P to P₂O₅
(D-013). Valueflows entities: `Agent` with recursive nesting,
`ResourceSpecification`, `EconomicResource`, `ProcessSpecification`,
`Process`, `Recipe*`, `Intent`, `Commitment`, `EconomicEvent`, and the action
behaviour table. No persistence.
*Answerable:* "what does this world contain, and what is on hand where?"

**M2 — Needs.**
Expression language — AST, validator, evaluator, JSON serialization.
`NeedStandard` with mandatory citation and declared attribute dependencies
that fail loudly rather than defaulting to zero. `ResponseModel` as a distinct
type, off by default.
*Answerable:* "how much food energy does Northsetting require this year, under
which standard, citing what?"

**M3 — Costing.**
`CostVector` with no scalar reduction. Named attribution rules for joint
products, carried in every result. Rollup through the recipe graph.
*Answerable:* "what does this loaf carry, in kg P and labour-hours and
ha·season, under which attribution rule?"

**M4 — Forward propagation.**
Time-stepped supply-driven propagation with Liebig limiting-factor
computation and explicit recipe lags. Ecosystem agents with stock balances
(soil phosphorus, water). Shortfall vectors per agent per period.
*Answerable:* **the reference question.**

**M5 — Branches and reproducibility.**
`World` and `Branch` with content-addressed delta storage. Scenario export.
The determinism test: same scenario, two runs in-process and one in a
subprocess under a different `PYTHONHASHSEED`, byte-identical output.
*Answerable:* "here is my scenario file — run it yourself and tell me where we
disagree."

**M6 — Seed world and CLI.**
The synthetic reference region as a generator plus sourced coefficient tables.
A CLI to load a world, apply assumptions, run forward, and export.
*Answerable:* everything above, by someone who is not the author.

### Explicitly not in v1

No web UI. No authentication. No federation. No signatures. No solver. No
database — worlds load from files and export to files.

A UI over a wrong kernel makes wrong answers persuasive, which for this
project is worse than no answers.

---

## v2 — more than one person, more than one place

**Milestones**

- **Persistence.** Postgres adapter, append-only, with `author_agent`,
  `signature`, and `prev_hash` columns present from the first migration and
  unenforced (D-010).
- **Signatures.** Per-agent Ed25519 keypairs, per-agent hash chains,
  explicitly not one global chain. Mirrors verify signatures and chain
  continuity. Conflicts are surfaced, never auto-resolved.
- **Coefficient audit.** The "why does this farm claim ten times the labour"
  workflow: mechanical diff of one agent's recipe coefficients against
  another's, with provenance for each.
- **Model refinement.** Materialised commitment-vs-event divergence with
  trend, surfaced for human revision of coefficients. Never auto-fitted.
- **Backward propagation.** Valueflows' `dependent-demand` explosion, for the
  demand-driven direction.
- **Read API and a minimal UI.** Once the kernel is trustworthy.

*Answerable:* "several communities are keeping records; where do our models
disagree, and has anyone quietly changed a coefficient?"

---

## v3 — more than food

- **Transport.** `pickup` / `dropoff` recipes, routes, vehicle-hours, fuel.
  The first real test of whether the ontology generalises past storable goods.
- **Energy.** Integration with PyPSA or Calliope rather than reimplementation.
  Energy as an input constraint on every other process.
- **Raw materials and manufacturing.** Extraction, refining, fabrication.
  Mostly a coefficient-data problem, not a modelling one.
- **Enumeration and the frontier.** Non-dominated option sets, needing a
  solver (HiGHS or OR-Tools). Still unranked (D-004).

*Answerable:* "can this region feed, move, power, and equip itself, and what
binds first?"

---

## v4 — federation

- Cross-instance federation. Independently grown instances merge as a union of
  per-agent logs — no global ordering, no consensus.
- Recursive aggregation across instances: net balance for a whole branch of
  the agent tree, at any depth, so a higher level can see "this sub-federation
  runs a long-run calorie deficit" without modelling its internals (D-009).

---

## Known model gaps

Tracked separately in [`model-gaps.md`](model-gaps.md), because they are
limits on what the answers mean rather than features not yet built. The two
that most distort the reference question:

- **G-001**, no nitrogen, so legume rotation has no benefit and forage looks
  worse than it is.
- **G-002**, food energy is the only nutrient modelled, which undervalues
  animal products and pulses.

Both are mostly coefficient work rather than engine work.

---

## Non-goals, permanently

- An objective function, or any capacity to choose between allocations (D-001).
- Currency, credits, labour-time accounting, or any universal equivalent
  (D-002).
- In-system voting or consensus mechanics (D-011).
- Blockchain or global consensus (D-010).
- Priority, urgency, or vulnerability scores.
