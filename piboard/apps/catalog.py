"""
Static app catalog — single source of truth for all app identities.

Consumed by:
  state.py               — _default_state() defaults, load() fallback & validation
  web/server.py          — _KNOWN_APPS validation set, render context for app switcher
  web/templates/index.html — Jinja2 app switcher buttons (via render context)
  web/static/app.js      — DEFAULT_APP_ID injected via template <script> block

Do NOT add dynamic discovery, importlib, or project imports here.
This module must remain free of circular dependencies.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class AppSpec:
    app_id: str           # machine identifier; must match registry key
    label: str            # full label shown in desktop sidebar
    short_label: str      # abbreviated label shown in mobile nav
    icon: str             # single emoji / symbol
    default_layout: str
    default_slots: tuple  # immutable; cast to list at consumption sites
    default_app_settings: tuple  # tuple of (key, value) pairs; cast to dict at consumption sites


APP_CATALOG: list[AppSpec] = [
    AppSpec(
        app_id="uk_station",
        label="UK Station",
        short_label="Station",
        icon="🚂",
        default_layout="single",
        default_slots=("mock",),
        default_app_settings=(("color_theme", "amber"), ("animations_enabled", True)),
    ),
    AppSpec(
        app_id="system_status",
        label="System Status",
        short_label="Status",
        icon="◉",
        default_layout="single",
        default_slots=(),
        default_app_settings=(),
    ),
]

# Pre-built lookup structures — computed once at import time, zero runtime cost.
KNOWN_APP_IDS: frozenset[str] = frozenset(s.app_id for s in APP_CATALOG)
DEFAULT_APP_ID: str = APP_CATALOG[0].app_id
