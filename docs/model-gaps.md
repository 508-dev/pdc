# Model gaps

What the model does not represent, and what each omission does to its answers.

This document is deliberately public and kept current. A model whose limits are
harder to find than its outputs invites more confidence than it has earned, and
under D-010 the point is that people can check the work — which includes
checking whether the thing they are looking at models what they think it does.

Ordered by how much each distorts the reference question.

---

## G-001 — No nitrogen, so legume rotation has no benefit

**Status:** open. The most consequential gap.

Alfalfa is a legume: it fixes atmospheric nitrogen, and rotating it with
cereals sustains cereal yields. The model has no nitrogen, so alfalfa is
currently pure cost — it consumes phosphorus and water and returns feed, and
nothing else.

**What it does to the answers.** It makes forage look worse than it is. On
food energy alone, feeding alfalfa to cattle is a lossy pathway, because
trophic loss means the same phosphorus put into wheat feeds more people. The
model therefore reports that concentrating phosphorus on grain maximises
calories. That is true given what is modelled, and incomplete: it is precisely
why real mixed-farming systems keep forage in rotation despite the loss.

**What would fix it.** A nitrogen stock per soil agent, a fixation output on
the alfalfa recipe, a nitrogen input on the cereal recipes, and yield response
to nitrogen availability. The lag machinery already handles the timing — the
benefit of this year's alfalfa lands on next year's wheat, which is the same
shape as the alfalfa-to-cattle lag already modelled.

Mostly coefficient work rather than engine work.

---

## G-002 — Food energy is the only nutrient modelled

**Status:** open.

`ResourceComposition` carries food energy and nothing else. Protein, fat, and
micronutrients are absent, and the Sphere standard's requirements for them
(10–12% of energy from protein, 17% from fat, micronutrient adequacy) cannot
currently be evaluated even though the standard is cited in full.

**What it does to the answers.** It undervalues animal products and pulses,
and overvalues starch. A community can appear adequately fed on calories while
being badly short of protein or iron, and the model will not say so.

**What would fix it.** Further nutrient specifications with their own
composition figures and their own standards. No engine change: they are more
rows, and they stay separate axes. Emphatically **not** rolled together into a
nutrition score — that would be D-002's failure mode in a lab coat, and it is
how "adequate diet" quietly becomes one number that can be traded against
other numbers.

---

## G-003 — Labour never binds

**Status:** open.

Labour is recorded on flows, typed by skill, and rolled up into cost vectors
correctly. It is not a constraint: forward propagation skips `work` flows when
computing the limiting factor, so a farm can run at any scale provided it has
the materials.

**What it does to the answers.** It overstates what every scenario can
achieve, and it hides the constraint that is most likely to bind in a real
syndicate. A plan that needs more field hours than the commune has people is
currently reported as feasible.

**What would fix it.** A workforce model: labour capacity per agent per period
by skill, which is a population question as much as a production one. Related
to the population model that D-008 puts outside `NeedStandard`.

---

## G-004 — No transport, and no transfers between communities

**Status:** open by design for v1; the assumption is stated on every run.

Outputs pool at the producing agent's community, and nothing moves between
communities. There are no roads, vehicles, fuel, distances, or delivery times.

**What it does to the answers.** It makes the model's distributional results
sharper than reality: Chakar goes to zero under the grain-first allocation
partly because nobody carries grain to it. In a real valley they might. The
model does not assume they would, because assuming a transfer is assuming an
allocation, and PDC does not make those (D-001).

**What would fix it.** `pickup` and `dropoff` recipes with vehicle-hours and
fuel, which the Valueflows action vocabulary already covers. A scenario that
wants to model a transfer should be able to state it as an explicit
assumption, the same way allocations are stated now.

---

## G-005 — Soil phosphorus only depletes

**Status:** open.

Cropping decrements the soil stock. Nothing replenishes it: no manure return,
no weathering, no crop residue, no imports. The model therefore describes a
valley mining its soil.

**What it does to the answers.** Over a long run it is too pessimistic, and it
misses the closed-loop reasoning that matters most to the project's politics —
manure from the dairy herd returning phosphorus to the fields is exactly the
kind of circularity a non-extractive system would build around.

**What would fix it.** Manure as a joint output of the dairy recipe, and a
recipe applying it to soil. Note this creates a production cycle, which
interacts with G-006.

---

## G-006 — Production cycles are reported, not resolved

**Status:** open, and blocking G-005.

`costing.rollup` walks the recipe graph backwards and raises
`CircularProductionError` when it meets a cycle. Real agricultural systems are
full of them: manure to soil to alfalfa to cattle to manure.

**What it does to the answers.** It does not distort them — it refuses to give
one, which is the right failure. But it means any circular system cannot be
costed at all.

**What would fix it.** A fixed-point solve rather than a walk. This is the
Leontief-style calculation the architecture anticipates, and it is the natural
place for the first real numerical method in the project.

---

## G-007 — Most coefficients are illustrative

**Status:** open, and the largest volume of work.

Twenty-one of twenty-six coefficients in the reference region are marked
`ILLUSTRATIVE` and refuse to be used by `Coefficient.check_usable()`. They are
plausible for a temperate semi-mechanised mixed-farming region and they are
not measured, sourced, or specific to anywhere.

**What it does to the answers.** Every number the model produces about the
reference region is a demonstration of the machinery, not a claim about any
real place.

**What would fix it.** Sourced figures, ideally for a real region someone
cares about. This is the most useful contribution anyone can make and needs no
programming — see `CONTRIBUTING.md`.
