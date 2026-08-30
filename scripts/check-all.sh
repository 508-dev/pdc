#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
./scripts/lint.sh
uv run ruff format --check src tests
./scripts/typecheck.sh
./scripts/test.sh
