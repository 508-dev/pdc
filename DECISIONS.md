# Decisions

Decisions that are expensive to reverse. Each entry states what was decided,
why, and what it forecloses. Append; do not silently rewrite. When a decision
is superseded, mark it and link forward rather than deleting it.

Established 2026-08-30 in the founding design session.

---

## D-001 — The software proposes, explains, and records. It never allocates.

PDC computes the state of a resource system, projects the consequences of
proposed changes, and records what actually happened. It does not choose
between feasible options, and it must not acquire the ability to.

When two communities need wheat and there is not enough wheat, the correct
behaviour is to show both communities exactly what each option costs whom, in
physical units, and stop. The choice is made by people, outside the software,
by whatever process they use.

**Forecloses:** an objective function. No `optimize()` entry point ships. See
D-004 for what the analysis layer is permitted to do instead.

**Why it is load-bearing:** the failure mode for a project like this is not
that it fails, it is that it succeeds as a benevolent-command ERP — a system
that claims to allocate by need while actually centralising authority in
whoever controls the data model, the weights, and the solver. Every other
decision here is downstream of refusing that.

---

## D-002 — Calculation is dimensional. Nothing reduces to a single scalar.

Costs, needs, and outcomes are carried as vectors of physically distinct
quantities — labour-hours by skill, kg P, m³ water, kcal, ha·season — and are
never collapsed into one number.

The rule, stated precisely:

> Aggregate freely **within** a dimension. Never reduce **across** dimensions.

Summing kcal across a region to say "this allocation costs the system 15% of
its calories" is legitimate: it is arithmetic inside one unit. Converting
kg of phosphorus into labour-hours so the two can be compared is not, at any
exchange rate, including a democratically chosen one.

This is Otto Neurath's position in the socialist calculation debate —
*calculation in kind*, `Naturalrechnung` — against Mises and Hayek. Neurath's
argument was that energy and raw-material constraints are genuinely
incommensurable, and that reducing them to one unit destroys information
rather than creating it. That is the epistemology of this project, and it is
the thing that distinguishes it from every adjacent effort.

**Forecloses:** currency, labour-time accounting, credits, mutual credit,
energy accounting, utility scores, priority scores, and any other universal
equivalent. There is no state, no class, and no currency.

---

## D-003 — Adopt Valueflows v1.0.0 as the ontology, minus its rollup algorithm.

[Valueflows](https://www.valueflo.ws/) reached its first stable release,
v1.0.0, in February 2026. It is the REA-derived vocabulary for economic
networks: agents, resources, processes, recipes, and the flow progression
`RecipeFlow → Intent → Commitment → EconomicEvent`. We adopt it as-is,
including its action vocabulary and its treatment of ecosystems as agents.

We reject exactly one part. Valueflows' own value-rollup algorithm states:

> "all of the input values need to be converted into the same unit: often, but
> not necessarily, a unit of money... In a time bank system, the unit would be
> hours."

That is the scalarization D-002 forbids. **We replace VF's rollup with a
dimensional rollup**: a cost vector that propagates through production and
never collapses. This is the project's actual technical contribution, and it
is the specific point where it diverges from Valueflows, from Cockshott's
labour-time accounting, and from Basis's credits.

**Forecloses:** using VF's rollup, cashflow, and value-equation algorithms as
specified. VF's dependent-demand, track/trace, and provenance algorithms are
adopted unchanged.

**See:** `docs/ontology.md` for the full mapping and the three concepts we add.

---

## D-004 — The analysis layer does feasibility, gap analysis, and enumeration.

Given D-001, the engine is permitted exactly three things:

1. **Feasibility** — is any allocation satisfying a given set of need
   standards possible with the resources on hand?
2. **Gap analysis** — which constraint binds, and by how much, in its own
   units? (Liebig's law of the minimum: the limiting factor is the answer, not
   an aggregate score.)
3. **Enumeration** — produce the set of non-dominated options, unranked.

Shadow prices are computable as an opt-in diagnostic, clearly labelled as an
artefact of one particular constraint set at one particular moment. They are
never persisted onto a resource and never used to compare options.

---

## D-005 — Simulation-first kernel. Reality is the branch humans author.

The core is a deterministic simulation kernel operating over branched worlds.
"Reality" is not a privileged data structure; it is simply the branch whose
events were authored by people rather than generated.

This falls out of needing three things from one system — live coordination for
a commune, scenario planning, and a simulation-game backend — and observing
that bolting simulation onto a live system later is a rewrite while the reverse
is not. It also means scenario exploration, counterfactuals, and replay are
free, and that the test suite exercises the real engine.

**Consequences:** determinism is a hard requirement, not a nice-to-have. No
wall-clock reads, no unordered iteration, no unseeded randomness anywhere in
the kernel. A scenario must serialize to a file that another person runs
against their own mirror and gets byte-identical results from. That
reproducibility is what makes "verify it with your own calculations" real
rather than aspirational.

---

## D-006 — Need is derived from cited standards, not declared as requests.

Valueflows has no concept of need. It has `Intent`, which is something an
agent *declares*. We add a layer above it.

A **NeedStandard** is a named, authored, cited, versioned expression mapping
agent attributes (population, age-sex structure, climate) to a requirement
vector. `Sphere-2018-survival`, `USDA-DRI-adult-female`, and
`Northsetting-Commune-2027-comfortable` are all just standards. A community
declares which ones it wishes to be evaluated against; the system reports
current state against each.

**There is no built-in ladder of tiers and no privileged standard.** An earlier
draft of this design hardcoded four tiers (survival / healthy / comfortable /
abundant) as a core enum. That was rejected as premature prescription. Tiers,
where communities want them, are simply several standards that someone chose
to publish and order.

**A standard with no citation and no author is a validation error.**

---

## D-007 — Need standards are a total, pure expression language, not code.

Standards are serialized expression trees — arithmetic, comparison,
conditionals, bounded summation over declared brackets, references to agent
attributes and to other standards. No loops, no recursion, no I/O, guaranteed
termination.

The reason is not purity, it is the cost of a second implementation. If a
standard is Python, verifying it means running *our* Python, with our
interpreter, our dependencies, our version — and independent verification
collapses into trusting our toolchain. If a standard is a twenty-node
expression tree, anyone can re-derive it in Rust, in a spreadsheet, or on paper
in an afternoon. **The restriction exists to make independent verification
cheap enough that people actually do it.**

Smart contracts are the cautionary tale, not the model. Turing-completeness
produced a world where essentially nobody reads the contract, verification is
outsourced to a priesthood of audit firms, and "code is law" produced the DAO.
That is the authority you removed from the planner reappearing as authority
over the toolchain.

---

## D-008 — NeedStandard and ResponseModel are separate object types.

A **NeedStandard** says what a community requires. A **ResponseModel** says
what happens when it does not get it — reduced labour output, malnutrition,
mortality.

These are different kinds of claim and must not share a type. The second is an
assertion about what happens to human beings when they are hungry, and it is
where the command-system risk reappears wearing a lab coat: a commune could
find the software asserting that its members underperform because they are
underfed, and that assertion feeding into next year's allocation. Nobody would
design that deliberately. It would simply be the default.

**ResponseModel is opt-in, named, cited, and off by default.** The default
behaviour on unmet need is to report the shortfall in physical units and stop.
Simulation and game uses want the feedback loop and should switch it on. A
live commune should have to choose it.

Population dynamics — including mortality and its absorbing states — live in
the population model, not in the need standard. NeedStandard stays a pure
function of current attributes.

---

## D-009 — Recursive agents. Federation is aggregation at a different depth.

An agent can contain agents, and every need, balance, and shortfall query is
defined to work at any depth of the tree. A household nests in a commune,
which nests in a valley, which nests in a region.

This makes the eventual federated view a query parameter rather than a
separate subsystem: "this branch of the tree is at net calorie loss long-run,
inject at that level and let it distribute internally" is one query with a
depth argument, not a new aggregation engine.

It is also Stafford Beer's Viable System Model recursion principle — every
viable system contains and is contained in viable systems, and variance is
absorbed at the lowest level that can absorb it. It is the strongest available
answer to "how is this not central planning": the higher level never needs to
model the lower level's internals.

Cheap now, unaffordable later.

---

## D-010 — Auditability by reproducible computation first; signatures second.

Two different guarantees, often confused:

- **Signatures** prove *who asserted this*.
- **Reproducible public computation** proves *whether the assertion is
  plausible*.

The motivating scenario — "this farm is requesting ten times the labour of any
comparable farm; which variable are they tweaking?" — is entirely the second.
It is answered by diffing their recipe coefficients against yours,
mechanically, because coefficients and standards are public declarative
expressions (D-007). That lands in v1.

Signatures are v2. The design is **per-agent Ed25519 keypairs with a per-agent
hash chain** — explicitly *not* one global chain. Each agent chains only its
own events, so two independently grown instances federating is a union of
agent logs with no global ordering to reconcile and no consensus to reach.

**But the schema carries `author_agent`, `signature`, and `prev_hash` from the
first migration**, nullable and unenforced. Retrofitting a hash chain onto an
existing event log requires rewriting history, which is the exact thing the
chain exists to prevent.

**Forecloses:** blockchain, global consensus, proof-of-anything. A 51% attack
means capital aggregation can overrule community consensus, which is the
failure this project exists to avoid. Openly analysable databases that anyone
can mirror, fork, and independently recompute are strictly better here.

---

## D-011 — Consensus mechanics are out of scope.

The system does not model votes, blocking, quorum, or delegation. It publishes
state, projects consequences, and records outcomes. People argue elsewhere and
report what they decided.

A decision protocol, if anyone wants one, is a plugin that consumes published
state and emits an outcome. The system's contribution to fair decisions is the
quality and auditability of the shared picture, not a mechanism.

**Forecloses:** an in-system voting or governance module.

---

## D-012 — Pure Python core. Framework shells are peripheral.

The kernel is a pure Python library with no framework dependency: ontology,
expression evaluation, propagation, and scenarios operating on plain objects.
Persistence, HTTP, and any eventual UI are adapters over it.

Python because the ecosystem this project will need — HiGHS, OR-Tools,
NetworkX, pint, and later PyPSA or Calliope for energy — lives there and none
of it should be rewritten. Frameworkless because the CLI simulator and the
eventual game backend must not import Django, and because a determinism-
critical kernel whose tests run with no database is worth a great deal.

---

## D-013 — SI units throughout, with substance-aware types.

Metric everywhere. `kcal` is retained alongside `MJ` because nutrition
literature is universally in kcal.

Critically, units are **substance-aware and refuse to add across conventions**.
Agronomy reports phosphorus as P₂O₅ and potassium as K₂O; soil science uses
elemental P and K; the conversion is ×2.29. Nitrogen and crude protein differ
by ×6.25. A model that silently mixes conventions overstates phosphorus by a
factor of two and every downstream number still looks reasonable.

These are distinct types that raise on addition, not a warning in the docs.
Air Canada 143 glided into Gimli because ground crew fuelled in pounds during
Canada's metric transition; the Mars Climate Orbiter was lost to pound-force
versus newton seconds. Both are unit-type errors a type system catches.

---

## D-014 — AGPL-3.0.

Network copyleft is the operative clause: it prevents a proprietary hosted
fork of a community's own allocation system. It also keeps us compatible with
the ecosystem worth drawing from — Open Food Network is AGPL, hREA is
Apache-2.0.

The Peer Production License and CNPL were considered and rejected. They are
non-free by OSI and FSF standards, which would block taking code from OFN and
deter contributors, in exchange for a symbolic statement. For a project whose
entire premise is that anyone may mirror, fork, and independently verify, a
restrictive licence works against itself. Politics belong in this file and in
the README, not in the licence.

Commercial use by capitalist enterprises is not a concern worth engineering
against.

---

## D-015 — Name: PDC. Provisional.

Production and Distribution Coordination, the Odonian institution in Le Guin's
*The Dispossessed*. Preferred over "Cybersyn" because Cybersyn was Stafford
Beer advising Allende's *state*, whereas PDC was a federation of syndicates
with no state at all — and because the name Cybersyn is now also a
venture-funded data-as-a-service company.

The name is provisional, and the objection to it is recorded because it is a
design constraint: in the novel, PDC is quietly capturable by informal
influence. Sabul steers Shevek's postings while the system appears neutral.
The structural answer to that is D-010 — a record that is public, mirrorable,
and independently recomputable, so that a thumb on the scale leaves a trace.
The literary criticism of PDC is precisely the threat model.

The git repository remains `cybersyn` for now; the Python package is `pdc`.

---

## Superseded

**Four-tier need ladder as a core enum** — proposed and rejected during the
founding session, before implementation. Superseded by D-006. Recorded because
the reasoning matters: a fixed ladder makes cross-community comparison easy
and makes the system prescriptive about what a good life requires. The second
cost outweighs the first, and the comparability is recoverable by communities
sharing standards rather than by the schema imposing them.
