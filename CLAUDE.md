# Claude Code Instructions

The canonical agent instructions are in `AGENTS.md`. Read it, and read
`DECISIONS.md` before any design-affecting change.

The three constraints most easily violated by well-meaning improvements:

1. **Never reduce across dimensions.** No function returns a single number
   summarising heterogeneous physical quantities. `CostVector` has no
   `.total()`, deliberately.
2. **The kernel is deterministic.** No clocks, no unseeded randomness, no
   order-dependent iteration, no I/O under `src/pdc/` outside `cli/`.
3. **Units are substance-aware.** kg P ≠ kg P₂O₅. Never coerce.

If a request would violate a decision in `DECISIONS.md`, say so before
implementing it.

Repo conventions: `uv run` for Python, repo scripts over raw commands, read
before editing, keep changes scoped, cite every physical coefficient, use the
gitignored `.context/` for scratch and promote durable knowledge into tracked
docs.
