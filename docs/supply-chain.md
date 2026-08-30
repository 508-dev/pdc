# Dependency Supply-Chain Policy

## Cooldown

New dependency releases are not adopted for seven days. This is a cheap
defence against the compromised-release attack pattern, where a malicious
version is published and yanked within hours.

`pyproject.toml`:

```toml
[tool.uv]
exclude-newer = "P7D"
```

Relative durations require **uv ≥ 0.9.17**. Before adding or changing this,
run:

```bash
uv --no-config --version
```

`--no-config` is used so a broken user-level config does not mask the real
version. Older uv clients fail during settings discovery when they encounter
`P7D`, so do not write it into config that an older client must parse.

Renovate applies the same window via `minimumReleaseAge: "7 days"` in
`renovate.json`.

## Locked installs

Lockfiles are committed. CI installs with `uv sync --locked`, which fails
rather than silently resolving something new.

## Version pinning

`requires-python` and the CI Python version are pinned and kept in step. A
local/CI skew is the classic way a lockfile-mismatch failure hides until an
unrelated PR trips it.

## Adding a dependency

The kernel's dependency surface is deliberately small: a determinism-critical
library whose transitive tree is large is hard to audit and hard to reproduce.
Adding a runtime dependency to anything under `src/pdc/` outside `cli/` and
adapters deserves an explicit justification in the PR.

Nothing in the kernel may depend on a package that reads the clock, the
network, or the environment at import time.
