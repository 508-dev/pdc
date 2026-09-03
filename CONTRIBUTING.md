# Contributing

PDC is early. The most useful contributions right now are argument and
domain data, not code.

## Before you change anything

Read [`DECISIONS.md`](DECISIONS.md). It records commitments that are expensive
to reverse, and each entry states what it forecloses. Several of them rule out
changes that would otherwise look like improvements:

- No objective function, and no capacity for the software to choose between
  allocations.
- No currency, credits, labour-time accounting, priority scores, or any other
  universal equivalent.
- No function that reduces heterogeneous physical quantities to one number.
- No in-system voting or consensus mechanics.
- No blockchain or global consensus.

If you think one of these is wrong, that is a conversation worth having — open
an issue and make the argument. Do not open a PR that quietly relaxes one.

## What is most wanted

- **Coefficients with citations.** Yields, nutrient contents, labour
  requirements, conversion factors, process durations and lags. Every number
  needs a source. This is the real bottleneck.
- **Need standards.** Published, cited, versioned standards other communities
  could adopt or argue with.
- **A second implementation of the expression evaluator**, in any language.
  The entire auditability model rests on that being cheap; someone doing it is
  the proof.
- **Reading the prior art** in [`docs/prior-art.md`](docs/prior-art.md) and
  telling us where we have got something wrong about it.
- **Closing a gap** from [`docs/model-gaps.md`](docs/model-gaps.md). G-001
  (nitrogen fixation) and G-002 (protein and micronutrients) are the two that
  most change what the model's answers mean.

## Coefficients must be cited

Any number describing the physical world carries its source — a document, DOI,
dataset, or a recorded deliberation. An uncited coefficient is a bug, not a
TODO. Where a plausible-but-unsourced figure is genuinely needed for a test
fixture, mark it explicitly as illustrative so it never migrates into a real
model.

## Local checks

```bash
./scripts/lint.sh
./scripts/typecheck.sh
./scripts/test.sh
./scripts/check-all.sh   # before opening a PR
```

The determinism test is not optional and must not be skipped or marked xfail.
If it fails, something in the kernel became order- or clock-dependent, and
that breaks the reproducibility that the project's auditability rests on.

## Pull requests

Use the template. Say what changed, why, and how you validated it. If the
change touches a decision, say which one and how it stays inside it.

Do not commit local state: `.venv`, caches, raw logs, or `.context/`.

## Licence

Contributions are under AGPL-3.0.
