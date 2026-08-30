"""The kernel must not depend on its shells.

docs/architecture.md section 1: dependencies point downward only. The kernel
is importable and fully exercisable with no framework, no database, and no
network — which is what makes the determinism guarantee testable at all.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

SOURCE_ROOT = pathlib.Path(__file__).resolve().parent.parent / "src" / "pdc"

KERNEL_PACKAGES = ("units", "ontology", "needs", "seed")
SHELL_PACKAGES = ("cli",)

FORBIDDEN_IN_KERNEL = {
    "django",
    "fastapi",
    "flask",
    "sqlalchemy",
    "psycopg",
    "psycopg2",
    "requests",
    "httpx",
    "aiohttp",
}

# Modules whose presence in the kernel would let a clock, the environment, or
# the network leak into a computation and quietly break reproducibility.
FORBIDDEN_NONDETERMINISM = {"random", "time", "datetime", "socket", "urllib", "secrets", "uuid"}


def _kernel_modules() -> list[pathlib.Path]:
    return sorted(
        path for package in KERNEL_PACKAGES for path in (SOURCE_ROOT / package).rglob("*.py")
    )


def _imported_roots(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_there_are_kernel_modules_to_check() -> None:
    """Guard against the sweep silently finding nothing."""
    assert len(_kernel_modules()) >= 8


@pytest.mark.parametrize("path", _kernel_modules(), ids=lambda p: p.name)
def test_kernel_does_not_import_shells(path: pathlib.Path) -> None:
    source = path.read_text()
    for shell in SHELL_PACKAGES:
        assert f"pdc.{shell}" not in source, f"{path.name} imports the {shell} shell"


@pytest.mark.parametrize("path", _kernel_modules(), ids=lambda p: p.name)
def test_kernel_has_no_framework_dependencies(path: pathlib.Path) -> None:
    offending = _imported_roots(path) & FORBIDDEN_IN_KERNEL
    assert not offending, f"{path.name} imports {sorted(offending)}"


@pytest.mark.parametrize("path", _kernel_modules(), ids=lambda p: p.name)
def test_kernel_cannot_read_a_clock_or_the_network(path: pathlib.Path) -> None:
    """D-005: no wall-clock reads, no unseeded randomness, no I/O."""
    offending = _imported_roots(path) & FORBIDDEN_NONDETERMINISM
    assert not offending, f"{path.name} imports {sorted(offending)}"
