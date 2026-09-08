"""Test configuration.

Django is configured here rather than through pytest-django: the explorer has
no database, no migrations, and no fixtures, so the plugin would buy nothing
and add a dependency.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def _configure_django() -> None:
    """Set up Django once, if it is installed.

    Skipped silently when the optional web extra is absent, so the kernel's
    own test suite still runs in an install without a web stack.
    """
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pdc.web.settings")
    try:
        import django
    except ModuleNotFoundError:
        return
    django.setup()
