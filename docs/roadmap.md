# Roadmap

Milestones are defined by what becomes *answerable*, not by what gets built.
No dates: this is a long evening project.

---

## v1 — the reference question — **done**

**Criterion, met:** the synthetic reference region loads, and PDC answers the
motivating question end to end — allocate the phosphorus one way or another,
run three years forward with the alfalfa-to-cattle lag, report the calorie
outcome per community per year against each community's declared standards,
and export both scenarios byte-reproducibly.

### Milestones

- **M1 — Units and ontology.** ✅ `pint` registry with substance-aware types
  that refuse to add P to P₂O₅; Valueflows entities with recursive agent
  nesting and the action behaviour table.
- **M2 — Needs.** ✅ Total expression language with JSON serialisation;
  `NeedStandard` with mandatory citation and declared dependencies that fail
  loudly; `ResponseModel` as a distinct type, off by default.
- **M3 — Costing.** ✅ `CostVector` with no scalar reduction, enforced rather
  than documented; named attribution rules for joint products, with no
  default.
- **M4 — Forward propagation.** ✅ Liebig limiting-factor computation,
  explicit recipe lags, ecosystem stocks, consumption against a named
  standard, and the `Cause` tree as a kernel output.
- **M5 — Branches and reproducibility.** ✅ Content-addressed delta storage,
  scenario export, independent verification that distinguishes "your code is
  wrong" from "you believe different coefficients", and the determinism proof
  over a full export.
- **M6 — Seed world and CLI.** ✅ Reference region with sourced-or-marked
  coefficients; `region`, `coefficients`, `standards`, `cost`, `compare`,
  `explain`, `export`, `verify`.

### What v1 found

The reference question's answer was not the one the fixture was built to
illustrate, and the fixture was not adjusted until it was. Concentrating
phosphorus on grain produces more food energy valley-wide *and* takes Chakar
to zero, because Chakar has no grain farm and its only food arrives through
alfalfa and the dairy herd.

That is the case for D-002 made by the model on its own data: a valley-wide
figure would report the aggregate improvement and hide the community that got
nothing. See `model-gaps.md` G-001 for the mechanism — legume nitrogen
fixation — that the model still lacks.

---

## v1.5 — the explorer

A web interface, because the audit right in D-010 is only real if checking the
work does not require a terminal. A tool usable solely by the CLI-literate
reproduces expert authority — the same shape as the audit-firm priesthood that
D-007 exists to avoid, with programmers in the role.

**Django and HTMX, server-rendered, kernel running server-side.** One
implementation of the model, so the screen cannot disagree with it. Minimal
JavaScript, tolerant of poor connectivity, and self-hostable by a syndicate on
a cheap machine.

A static file reading an export was considered and rejected: it can display a
precomputed answer but cannot re-run anything, and the point is to let people
change an assumption and see what happens.

**No database.** A branch is an ordered set of named assumptions with a
content-addressed digest, so the URL *is* the scenario: assumptions encode into
the query string, the kernel runs, HTMX swaps the results fragment. Scenarios
are shareable and bookmarkable by construction, and persistence waits for v2
where it is actually needed.

### Milestones

- **M7 — Read-only views.** The region, declared need per community, the
  comparison table, and the `Cause` tree rendered as a walkable chain down to
  each cited coefficient. Renders `Cause.to_json()`; computes nothing.
- **M8 — Assumption controls.** Adjust an allocation, a plan's scale, or the
  consumption standard, and see the outcome change. Every control maps to an
  `Assumption`, so anything the interface can express is also expressible as a
  branch, a URL, and an export.
- **M9 — Coefficient inspection and diff.** Follow any number in an
  explanation to its citation and provenance; compare one branch's
  coefficients against another's. This is the "why does this farm claim ten
  times the labour" workflow, and it is the reason the interface exists.
- **M10 — Export and verify in the browser.** Download the scenario you are
  looking at; upload someone else's and see where you disagree.

**Explicitly not in v1.5:** authentication, data entry, persistence,
multi-user anything. It is a lens over a world the kernel builds, not yet a
place to keep records.

*Answerable by someone who has never opened a terminal:* "what happens to my
community if we allocate the phosphorus differently, and which number in the
chain do I disagree with?"

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
- **Data entry and records.** The explorer becomes a place to record what
  actually happened, not only to project what might, which is what turns
  commitment-versus-event divergence from a design into a practice.

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
