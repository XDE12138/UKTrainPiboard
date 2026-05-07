"""
Static runtime assembly — single entry point for instantiating all apps.

Responsibilities:
  1. Call each app's setup function (explicit, static wiring).
  2. Construct each BaseApp instance.
  3. Validate that every app declared in APP_CATALOG has been assembled.
     If any catalog app is missing, raise RuntimeError at startup — fail fast,
     never enter a state where the UI accepts an app_id the host cannot run.

Rules:
  - Imports are static and explicit; no importlib, no dynamic discovery.
  - Per-app setup differences are preserved here, not abstracted away.
  - main.py consumes the result dict; it does not maintain its own inventory.
"""
from host.registry import Registry
from apps.catalog import KNOWN_APP_IDS
from apps.uk_station.setup import setup as setup_uk_station
from apps.system_status.setup import setup as setup_system_status


def assemble_apps(registry: Registry, providers: dict, app_state) -> dict:
    """
    Assemble and return {app_id: BaseApp instance} for every app in APP_CATALOG.

    Raises RuntimeError on startup if any catalog app has no wiring here.
    """
    instances = {}

    # --- uk_station ---
    uk_app_settings = app_state.get_app_settings("uk_station")
    layouts = setup_uk_station(registry, providers, uk_app_settings)
    UKStationApp = registry.get_app("uk_station")
    instances["uk_station"] = UKStationApp(
        layouts=layouts,
        providers=providers,
        initial_layout=app_state.get_app_layout("uk_station"),
        initial_slots=app_state.get_app_slots("uk_station"),
        initial_app_settings=uk_app_settings,
    )

    # --- system_status ---
    setup_system_status(registry)
    SystemStatusApp = registry.get_app("system_status")
    instances["system_status"] = SystemStatusApp()

    # Catalog alignment check — every KNOWN_APP_ID must have been assembled above.
    # If a new app is added to catalog.py but wiring is missing here, this raises
    # at startup before pygame or Flask start, preventing UI/host divergence.
    missing = KNOWN_APP_IDS - set(instances.keys())
    if missing:
        raise RuntimeError(
            f"Catalog apps not assembled: {missing}. "
            f"Add their wiring to apps/assembly.py."
        )

    return instances
