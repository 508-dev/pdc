"""Django settings for the explorer.

Deliberately small. There is no database, no authentication, no sessions, and
no user model, because there is nothing yet to persist or protect: the
explorer is a lens over a world the kernel builds, and every scenario it can
show is encoded in the URL.

That also means it holds no secrets. The SECRET_KEY below is a fixed
development value and is only used because Django insists on one — nothing
here signs cookies, and there are no cookies.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SECRET_KEY = os.environ.get("PDC_SECRET_KEY", "pdc-explorer-no-secrets-here")
DEBUG = os.environ.get("PDC_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("PDC_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS: list[str] = []

# No sessions, no auth, no messages: nothing here has a user. CSRF is kept
# because there is one POST — uploading someone else's export to diff against
# — and Django's implementation needs only a cookie, not a session.
MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]

ROOT_URLCONF = "pdc.web.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": False,
        "OPTIONS": {"context_processors": []},
    }
]

# Django accepts an empty mapping and will refuse any query, which is what we
# want: an accidental model import should fail loudly rather than silently
# creating state.
DATABASES: dict[str, dict[str, str]] = {}

# An uploaded export is read into memory to be parsed. Cap it: this endpoint
# takes a document from a stranger, and it is the only place the explorer
# accepts input it did not generate.
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_BYTES
FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_BYTES

USE_TZ = False
LANGUAGE_CODE = "en"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
