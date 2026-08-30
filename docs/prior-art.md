# Prior art

What exists, what to take from each, and where each one stops. Surveyed
2026-08-29/30. Status notes are from that date and will rot; re-check before
relying on them.

---

## Build on

### Valueflows — the ontology

<https://www.valueflo.ws/> · [Codeberg](https://codeberg.org/valueflows/valueflows) · CC-BY-SA 4.0

The REA-derived vocabulary for economic networks: agents, resources,
processes, recipes, and the `Intent → Commitment → EconomicEvent` progression.
**Reached v1.0.0, its first stable release, in February 2026** after roughly a
decade of drafts. Maintained by Lynn Foster and Bob Haugen (Mikorizal).

The GitHub repository is a tombstone; the project moved to Codeberg. The
system of record for the specification is the Turtle file at
`codeberg.org/valueflows/pages`.

Adopted as PDC's ontology (D-003). Its `rollup` algorithm is rejected; see
"Where everyone else stops" below. Its `dependent-demand`, `track`, `trace`,
and `provenance` algorithms are adopted unchanged.

### Otto Neurath — the epistemology

*Calculation in kind* / `Naturalrechnung`. Neurath's position in the socialist
calculation debate against Mises and Hayek: that a rational economy can be
planned in disaggregated physical magnitudes, and that energy and
raw-material constraints are genuinely incommensurable, so reduction to a
single unit destroys information rather than creating it.

This is PDC's stated epistemology (D-002), and the literature is the defence
of it. Starting points: Thomas Uebel, *"Calculation in kind and marketless
socialism: On Otto Neurath's utopian economics"* (European Journal of the
History of Economic Thought 15:3, 2008); and the *Calculation in kind*
entry as an orientation.

### Stafford Beer — the organisational form

Project Cybersyn (Chile, 1971–73) and the Viable System Model. The VSM's
recursion principle — every viable system contains and is contained in viable
systems, variance absorbed at the lowest level that can absorb it — is the
structure of PDC's recursive agent tree (D-009), and the strongest available
answer to "how is this not central planning."

Cybersyn is the political ancestor but not the model: it was Beer advising a
*state*. PDC is named for the Odonian federation of syndicates instead
(D-015).

---

## Learn from, do not join

### Basis — closest existing project

<https://basisproject.net/> · Andrew M. Lyon · Rust

A post-capitalist economic protocol extending Valueflows. Its central
innovation is **in-kind cost tracking**: costs recorded as dimensional objects
carrying labour-hours grouped by occupation, resources by type, and processes,
propagated through production without collapsing. Blocs (cooperative
groupings), stewardship rather than ownership, and no profit on markup.

That dimensional cost object is substantially what D-002 requires, arrived at
independently, and it is worth studying closely.

**Where it diverges:** Basis retains consumer credits — destroyed on purchase,
but credits — and keeps prices as a demand signal. PDC rejects both. No state,
no class, no currency.

Paper is at v3.0 (March 2024) with several sections still marked TODO
(voting, bankruptcy, tracker governance, investment).

### hREA — Valueflows on Holochain

<https://hrea.io/> · [h-REA/hREA](https://github.com/h-REA/hREA) · Apache-2.0

The most complete Valueflows backend, with a GraphQL adapter. Actively
developed. Core described as stable for beta use; API usability around 70%
complete.

Worth reading as a reference implementation of the vocabulary. The Holochain
substrate is not wanted here — PDC's position is that the problem is
semantics, governance, data quality, and UX, not consensus, and that openly
mirrorable databases anyone can recompute beat any consensus mechanism for
this purpose (D-010).

### Zenflows / Interfacer / Reflow — complete VF implementations

Dyne.org, Elixir. Listed by Valueflows as *complete* implementations covering
urban material flows, circular economy, and Fab City production. The most
mature non-Holochain VF codebases; read for how the vocabulary survives
contact with production.

### Cockshott, Cottrell, Dapprich — the scalarizing camp

*Towards a New Socialism* (1993) and successors, including Dapprich's work
adding ecological constraints and opportunity-cost shadow prices, and a joint
book bringing the three together on planning under climate crisis.

Technically substantial and worth knowing: Cockshott's "harmony algorithm"
reportedly scales around *n·log n* where simplex is around *n³*, which matters
at national scale. Dapprich argues shadow prices measure opportunity cost
better than labour time because they account for constraints — such as limited
natural resources — that cannot be reduced to labour.

**This is precisely the camp PDC departs from**, and the departure should be
made deliberately rather than by ignorance. Their output is the one true plan,
computed. PDC's output is a shared picture that people argue over. Both
scalarize; PDC does not.

### Participatory Economy Project — PPIP

<https://participatoryeconomy.org/>

Building a Participatory Planning Interactive Prototype: software letting
people take part in a simplified annual participatory planning procedure.
Source intended to be opened but not yet public as of last announcement.
Worth tracking — the closest active effort on the *deliberation* side, which
PDC deliberately does not build (D-011).

---

## Steal domain knowledge from

### Open Food Network

[openfoodfoundation/openfoodnetwork](https://github.com/openfoodfoundation/openfoodnetwork) · Rails · AGPL-3.0 · very active

Mature, real, in production across many countries: producers, hubs, stock,
food-specific units, orders, pickup and delivery, local distribution. Market
and e-commerce oriented, so not an allocation model — but the accumulated
domain knowledge about how food actually moves is worth a great deal, and the
licence is compatible.

### OpenBoxes

[openboxes/openboxes](https://github.com/openboxes/openboxes) · very active

Warehouse and inventory management built for resource-scarce healthcare
settings. The boring, essential logistics: lots, expiry, requisitions, stock
movements, shipments, stockouts. Where to look when PDC needs storage and
perishability done properly.

### ERPNext, Odoo

Capitalism already built most of the abstractions: bills of material,
routings, work orders, units of measure, substitutions, multi-level BOM
explosion. Read the abstractions, discard the accounting assumptions. Note
that Valueflows' recipe layer already generalises most of this.

---

## Data sources

| Source | For | Notes |
| --- | --- | --- |
| [Sphere Handbook](https://spherestandards.org/handbook/) | Survival-tier food standard | 2,100 kcal/person/day, 10–12% protein, 17% fat, plus micronutrient adequacy. A citable minimum with an established methodology. |
| USDA FoodData Central | Food composition | ~300k foods, 140+ nutrients. Bulk download and API (`api.nal.usda.gov/fdc/v1/`, needs a free data.gov key). Foundation and SR Legacy are the useful subsets; Branded is retail noise. |
| Dietary Reference Intakes | Adequacy standards by age and sex | The basis for "healthy" standards as distinct from survival. |
| FAO / FAOSTAT | Yields, food balance sheets, crop coefficients | Regional production coefficients. |
| EXIOBASE | Environmentally-extended multi-regional input-output | For eventual whole-economy material flow work. |
| [PyPSA](https://pypsa.org/), [Calliope](https://www.callio.pe/), OSeMOSYS | Energy system modelling | Mature and open, urban-district to continental scale. **Integrate; do not reimplement.** |
| openLCA, Brightway2 | Life-cycle assessment, material flow analysis | For process coefficient sourcing. |

---

## Where everyone else stops

Every adjacent project eventually converts everything into one unit.

- **Valueflows** — money, or hours in a time bank, or credits. Explicitly
  agnostic about which; not agnostic about there being one.
- **Basis** — labour credits, destroyed on purchase, with prices as demand
  signal.
- **Cockshott and Cottrell** — labour time.
- **Dapprich** — shadow prices from linear optimisation.
- **Participatory economics** — effort ratings and indicative prices from
  iterated planning rounds.
- **Conventional ERP** — money, obviously.

That common terminus is what PDC declines. The cost of declining it is that
the software cannot choose between options — which is D-001, and is the point
rather than a limitation.
