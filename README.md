# PDC

**Production and Distribution Coordination** — software for organising
resources and labour by need, in physical units, without a currency.

Post-capitalist resource coordination: model what a community needs, what a
region can produce, and what any proposed allocation costs whom — then show
that to everyone and let people decide. It is a calculator and a shared
picture, not an allocator.

Named for the Odonian institution in Ursula K. Le Guin's *The Dispossessed*.
Early, and pre-alpha: there is a design, and it is being built.

---

## The idea

A town of 25,000 needs a certain number of calories, and a certain amount of
iron and protein and water. Producing that requires particular farms, and
those farms require phosphorus and labour and land, and the phosphorus and the
labour come from somewhere too. All of that is calculable from public data.

What is *not* calculable is who should get the wheat when there is not enough
wheat. PDC does the first part and refuses the second.

So the output is not a plan. It is an argument-grade picture:

> If we direct all the phosphorus to farm A, farm B will not produce the
> alfalfa that ranches C and D need the year after, which costs the system 50%
> of its calories. If we split the phosphorus, the loss is 15%.

Everyone can see that, everyone can check the arithmetic against their own
copy of the data, and then people decide — by whatever process they use,
outside the software.

## What makes it different

Nearly every adjacent project — Valueflows' own rollup, Basis, Cockshott's
labour-time accounting, participatory economics, and obviously conventional
ERP — eventually converts everything into one unit so that options can be
ranked. Money, or hours, or credits, or shadow prices.

PDC does not. Costs and needs are carried as **vectors of physically distinct
quantities** — labour-hours by skill, kg of phosphorus, m³ of water, kcal,
hectare-seasons — and are never collapsed:

> **Aggregate freely within a dimension. Never reduce across dimensions.**

Summing calories across a region is arithmetic. Converting phosphorus into
labour-hours is a value judgement, and it belongs to people rather than to a
solver. This is Otto Neurath's *calculation in kind*, expressed as a data
structure.

The cost of that choice is that the software cannot choose between options.
That is the point, not a limitation.

## Design commitments

- **The software proposes, explains, and records. It never allocates.** No
  objective function ships.
- **No currency, credits, labour-time accounting, or priority scores.** No
  universal equivalent of any kind.
- **Need is derived from cited standards, not from requests.** A standard with
  no citation and no author is a validation error. There is no built-in ladder
  of tiers and no privileged standard.
- **Standards are a total expression language, not code** — so that anyone can
  re-derive them in another language, in a spreadsheet, or on paper. Cheap
  independent verification is the whole auditability model.
- **Simulation-first.** Reality is simply the branch whose events people
  authored. Scenarios are reproducible byte-for-byte on any mirror.
- **Recursive agents.** Households nest in communes nest in valleys. Federation
  is aggregation at a different depth, not a separate system.
- **No blockchain.** A 51% attack means capital aggregation can overrule
  community consensus, which is the failure this project exists to avoid.
  Mirrorable, forkable, independently recomputable databases are strictly
  better here.

Full reasoning, including what each decision forecloses, is in
[`DECISIONS.md`](DECISIONS.md).

## Built on

[Valueflows v1.0.0](https://www.valueflo.ws/) — the REA-derived vocabulary for
economic networks, stable since February 2026 — adopted as the ontology, with
its value-rollup algorithm replaced by a dimensional one. See
[`docs/ontology.md`](docs/ontology.md) for the exact mapping and the three
concepts PDC adds.

## Documentation

| | |
| --- | --- |
| [`DECISIONS.md`](DECISIONS.md) | What was decided, why, and what it forecloses |
| [`docs/ontology.md`](docs/ontology.md) | Valueflows mapping; NeedStandard, ResponseModel, CostVector |
| [`docs/architecture.md`](docs/architecture.md) | Layering, simulation kernel, propagation engine |
| [`docs/prior-art.md`](docs/prior-art.md) | What exists, what to take, where each stops |
| [`docs/roadmap.md`](docs/roadmap.md) | Milestones, defined by what becomes answerable |
| [`docs/model-gaps.md`](docs/model-gaps.md) | What the model does not represent, and what that does to its answers |

## Status

Pre-alpha. v1 is done when the synthetic reference region loads and the system
reproduces the phosphorus comparison above — three years forward, with the
alfalfa lag, exported and byte-reproducible on another machine. No UI, no
database, no authentication, no solver until then.

## Uses

Coordination for real communes; scenario planning; simulation; and a backend
for simulation games. These are the same system because reality is just the
branch with human-authored events.

## Licence

AGPL-3.0. Network copyleft is the operative clause: it prevents a proprietary
hosted fork of a community's own allocation data.
