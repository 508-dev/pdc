# Security Policy

## Threat model

PDC's threat model is unusual, so it is worth stating plainly.

**The data is meant to be public.** The database is designed to be dumped,
mirrored, forked, and recomputed by anyone. Confidentiality of resource and
production records is not a goal; publishing them is the point. There are no
secrets in the system by design.

The attacks that matter are therefore about **integrity and influence**, not
disclosure:

- Silently altering a coefficient so one agent's claimed requirements or
  yields diverge from reality without anyone noticing.
- Forging events attributed to another agent.
- Presenting a computation that cannot be independently reproduced, so that
  the tool has to be trusted rather than checked.

The countermeasures are structural rather than defensive: declarative, public
need standards and coefficients that anyone can diff (v1); deterministic,
byte-reproducible scenarios (v1); and per-agent signatures over per-agent hash
chains (v2). See D-007 and D-010 in [`DECISIONS.md`](DECISIONS.md).

A system that has to be trusted has already failed, whatever its cryptography.

## Reporting

Do not open public issues for vulnerabilities. Report to the maintainers
privately via GitHub's security advisory feature on this repository.

Reports about *integrity* — a way to make the system produce unreproducible
results, or to attribute an event to an agent who did not author it — are as
serious as conventional vulnerabilities here, and more likely.

## Secret handling

There should be nothing to protect. If a deployment adds credentials, keep
them in environment variables or encrypted files and never in code. Never
commit real `.env` files, tokens, private keys, or credentials.

## Dependencies

- `uv`: `exclude-newer = "P7D"` cooldown; requires uv ≥ 0.9.17.
- Renovate: `minimumReleaseAge` of 7 days.
- CI uses locked installs (`uv sync --locked`). Lockfiles are committed.

## GitHub Actions

Least-privilege permissions, action SHAs pinned, `persist-credentials: false`
where practical, `harden-runner` in audit mode.
