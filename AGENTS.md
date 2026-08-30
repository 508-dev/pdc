# Agent Development Guide

Canonical operating instructions for agents working in this repository.
`CLAUDE.md` and `.cursor/rules/` point here.

## Read first

Before making design-affecting changes, read `DECISIONS.md`. It records
commitments that are expensive to reverse and states what each one forecloses.
Several of them rule out things that would otherwise look like obvious
improvements — an objective function, a priority score, a unit conversion
between labour and materials. **If a change would violate a decision, stop and
say so rather than implementing it.**

Then, by area: `docs/ontology.md` for the data model, `docs/architecture.md`
for layering and the kernel, `docs/roadmap.md` for what milestone we are in.

## The three rules most easily broken

1. **Never reduce across dimensions.** Aggregating kcal is fine. Converting
   kg P into labour-hours is not, at any exchange rate. If a function would
   return a single number summarising heterogeneous quantities, it is wrong.
   There is no `.total()` on a `CostVector` and adding one is not a
   contribution.

2. **The kernel is deterministic.** No wall-clock reads, no unseeded
   randomness, no iteration over unordered collections where order affects
   results, no I/O, no environment reads — anywhere under `src/pdc/` except
   `cli/` and future adapters. Sort at every boundary that feeds computation.

3. **Units are substance-aware.** kg P and kg P₂O₅ are different types and
   refuse to add (×2.29). Same for K/K₂O, N/crude protein, and fresh
   weight/dry matter. Conversions are explicit and named. Never coerce.

## Environment

- Only `python3` is guaranteed. Do not assume `python` exists.
- Use `uv run` for everything Python. Prefer repo scripts over raw commands.
- Treat install, dev, and test commands as executable code; inspect manifests
  and scripts before running them.

## Dependency supply-chain safety

- `uv`: `exclude-newer = "P7D"` in `pyproject.toml`. Relative durations require
  uv ≥ 0.9.17; run `uv --no-config --version` before touching this. Do not
  write `P7D` into config that an older uv must parse.
- CI uses locked installs: `uv sync --locked`.
- Commit lockfiles.

## Repository shape

- `src/pdc/` — the kernel and its shells. Layer order and import rules are in
  `docs/architecture.md` §1 and §7; a test enforces them.
- `tests/` — pytest. The determinism test is not optional and not skippable.
- `docs/` — contributor-facing documentation.
- `skills/` — project-local agent skills.
- `.context/` — gitignored workspace-local scratch. Not committed.

## Editing rules

- Read target files, callers, and tests before editing.
- Keep edits surgical. Do not reformat unrelated files.
- Add or update tests when behaviour changes.
- Update docs when a contract changes. A new decision goes in `DECISIONS.md`
  as a new entry; superseded decisions are marked and linked forward, never
  deleted.
- **Coefficients require citations.** Any number describing the physical world
  — a yield, a nutrient content, a labour requirement, a conversion — carries
  its source. An uncited coefficient in seed data or a need standard is a bug,
  not a TODO. Where a plausible-but-unsourced figure is genuinely needed for a
  fixture, mark it explicitly as illustrative.
- Keep secrets out of code. There should not be any secrets; the database is
  designed to be published.

## `.context/`

Workspace-local agent scratch only. Durable knowledge is promoted into tracked
docs — `DECISIONS.md` for decisions, `docs/` for everything else.

## Validation

```bash
./scripts/lint.sh
./scripts/typecheck.sh
./scripts/test.sh
./scripts/check-all.sh   # all of the above
```

## Tone

This project has a politics and the documentation states it plainly. Do not
sand that down into product-neutral language, and do not inflate it into
manifesto. Write like an engineer who has read the argument and found it
sound.
