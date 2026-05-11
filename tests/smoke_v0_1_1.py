#!/usr/bin/env python3
"""Minimal v0.1.1 smoke checks.

Run from the repository root:
  python3 tests/smoke_v0_1_1.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PIBOARD = ROOT / "piboard"
sys.path.insert(0, str(PIBOARD))

from board.content import BoardContent  # noqa: E402
from data.fetcher import DataFetcher  # noqa: E402
from main import build_providers  # noqa: E402
from providers.mock import MockProvider  # noqa: E402
from providers.train_bridge import TrainSourceBridge  # noqa: E402
from providers.weather_bridge import WeatherSourceBridge  # noqa: E402
from sources.weather import WeatherObservation  # noqa: E402
from web.server import create_app  # noqa: E402


def check_state_example_json() -> None:
    data = json.loads((PIBOARD / "data" / "state.example.json").read_text())
    assert data["schema_version"] == 1
    assert data["current_app"] == "uk_station"
    assert data["source_configs"]["train"]["data_source"] == "mock"
    assert data["source_configs"]["calendar"]["ical_url"] == ""


def check_mock_cycle_order() -> None:
    provider = MockProvider(
        config={
            "preset": "cycle",
            "cycle_presets": ["overview", "train", "weather", "calendar"],
            "refresh_interval_sec": 10,
        }
    )
    seen = [provider.fetch().provider_id for _ in range(4)]
    assert seen == ["mock:overview", "mock:train", "mock:weather", "mock:calendar"]


def check_train_mock_bridge() -> None:
    provider = TrainSourceBridge(config={"data_source": "mock", "station_crs": "KGX"})
    content = provider.fetch()
    assert isinstance(content, BoardContent)
    assert content.provider_id == "train"
    assert content.status_text == "DEMO"
    assert "mock" in content.footer.lower()


class _WeatherSourceStub:
    called = False

    def fetch(self) -> WeatherObservation:
        self.called = True
        return WeatherObservation(
            temperature=20,
            feels_like=19,
            description="Clear Sky",
            humidity=50,
            wind_dir="N",
            wind_speed_str="6km/h",
            visibility_km=10,
            uv_label="Low",
            forecast=[("Today", "22\u00b0C", "14\u00b0C"), ("Wed", "21\u00b0C", "13\u00b0C")],
            city="Test City",
            unit_sym="\u00b0C",
            fetched_at=1_700_000_000,
        )


def check_weather_no_key_uses_open_meteo_path() -> None:
    provider = WeatherSourceBridge(config={"api_key": "", "city": "Test City"})
    stub = _WeatherSourceStub()
    provider._source = stub
    content = provider.fetch()
    assert stub.called
    assert isinstance(content, BoardContent)
    assert content.provider_id == "weather"
    assert content.footer == "Open-Meteo"


def check_api_state_shape() -> None:
    providers = build_providers()
    fetcher = DataFetcher()
    try:
        app = create_app(providers, fetcher)
        client = app.test_client()
        state_resp = client.get("/api/state")
        assert state_resp.status_code == 200
        state = state_resp.get_json()
        assert state["schema_version"] == 1
        assert "apps" in state
        assert "source_configs" in state
        assert "device_settings" in state

        version_resp = client.get("/api/version")
        assert version_resp.status_code == 200
        version = version_resp.get_json()
        assert "version" in version
        assert "commit" in version

        device_resp = client.get("/api/device-status")
        assert device_resp.status_code == 200
        device = device_resp.get_json()
        assert device["ok"] is True
        assert "version" in device
    finally:
        fetcher.stop()


def main() -> int:
    checks = [
        ("state example JSON", check_state_example_json),
        ("mock cycle", check_mock_cycle_order),
        ("train mock bridge", check_train_mock_bridge),
        ("weather no-key path", check_weather_no_key_uses_open_meteo_path),
        ("API/state shape", check_api_state_shape),
    ]
    for name, fn in checks:
        fn()
        print(f"PASS {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
