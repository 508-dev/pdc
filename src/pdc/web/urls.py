"""URL routing.

Scenario and period are path segments rather than opaque identifiers, so that
a link to a particular reading is legible and can be pasted into a message.
When assumptions become adjustable, they encode into the query string and the
URL becomes the whole scenario.
"""

from __future__ import annotations

from django.urls import path

from pdc.web import views

urlpatterns = [
    path("", views.overview, name="overview"),
    path("compare/", views.compare, name="compare"),
    path("explore/", views.explore, name="explore"),
    path("htmx.js", views.htmx_script, name="htmx"),
    path(
        "explain/<str:scenario>/<str:agent_id>/<int:period>/",
        views.explain,
        name="explain",
    ),
]
