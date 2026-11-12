"""Release regressions: invalid writes must not mutate or persist state."""
import copy
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "piboard"))
from state import AppState
from providers.custom import CustomProvider
from providers.mock import MockProvider
from providers.calendar_bridge import CalendarSourceBridge
from providers.weather_bridge import WeatherSourceBridge
from web import server


class WriteValidationTests(unittest.TestCase):
    def setUp(self):
        self.state = object.__new__(AppState)
        self.state._init()
        self.providers = {p.provider_id: p for p in (
            CustomProvider(), MockProvider(), CalendarSourceBridge(), WeatherSourceBridge())}
        self.fetcher = Mock()
        self.patcher = patch.object(server, "app_state", self.state)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.client = server.create_app(self.providers, self.fetcher).test_client()

    def assert_rejected(self, url, payload):
        before = self.state.get_all()
        configs = {k: copy.deepcopy(p.config) for k, p in self.providers.items()}
        response = self.client.post(url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 400, (url, payload, response.status_code))
        self.assertIn("error", response.get_json())
        self.assertEqual(self.state.get_all(), before)
        self.assertEqual({k: p.config for k, p in self.providers.items()}, configs)
        self.fetcher.force_refresh.assert_not_called()

    def test_non_object_bodies(self):
        for url in ("/api/layout", "/api/app/uk_station/layout", "/api/settings",
                    "/api/device-settings", "/api/app/uk_station/settings",
                    "/api/source/custom/config", "/api/provider/custom/config",
                    "/api/current-app", "/api/orientation"):
            for payload in (None, [], "text", 1):
                with self.subTest(url=url, payload=payload):
                    self.assert_rejected(url, payload)

    def test_layout_ids_and_slot_shapes(self):
        for payload in ({"layout": "bad"}, {"slots": "mock"}, {"slots": [{}]},
                        {"slots": ["unknown"]}, {"slots": []}, {"slots": ["mock"] * 4}):
            for url in ("/api/layout", "/api/app/uk_station/layout"):
                self.assert_rejected(url, payload)

    def test_source_types_options_and_rows(self):
        for sid, payload in (("custom", {"title": []}), ("custom", {"ticker": None}),
                             ("custom", {"rows": [None]}), ("custom", {"rows": [{"left": {}}]}),
                             ("custom", {"rows": [{"left_color": []}]}),
                             ("custom", {"title_color": "bad"}), ("custom", {"unknown": "x"}),
                             ("mock", {"preset": []}), ("mock", {"cycle_presets": [{}]}),
                             ("mock", {"refresh_interval_sec": 0}),
                             ("calendar", {"lookahead_days": "bad"}),
                             ("calendar", {"lookahead_days": 1.5}),
                             ("weather", {"latitude": "nan"}), ("weather", {"units": []})):
            for url in (f"/api/source/{sid}/config", f"/api/provider/{sid}/config"):
                self.assert_rejected(url, payload)

    def test_combined_settings_are_validated_before_either_write(self):
        for url, payload in (("/api/settings", {"color_theme": "green", "brightness": "bad"}),
                             ("/api/settings", {"animations_enabled": "false"}),
                             ("/api/device-settings", {"brightness": float("nan")}),
                             ("/api/device-settings", {"brightness": True}),
                             ("/api/device-settings", {"brightness": 2}),
                             ("/api/device-settings", {"orientation": []}),
                             ("/api/app/uk_station/settings", {"color_theme": []}),
                             ("/api/current-app", {"app_id": []}),
                             ("/api/orientation", {"orientation": []})):
            self.assert_rejected(url, payload)

    def test_ws_canonical_and_compat_reject_before_mutation(self):
        for message in ([], {"action": "set_layout", "layout": "single", "slots": [{}]},
                        {"action": "set_app_layout", "layout": "bad", "slots": ["mock"]},
                        {"action": "update_source_config", "source_id": "custom", "config": {"title": []}},
                        {"action": "update_config", "provider_id": "custom", "config": []},
                        {"action": "update_device_settings", "device_settings": {"brightness": "bad"}},
                        {"action": "update_app_settings", "app_settings": {"animations_enabled": "false"}},
                        {"action": "update_settings", "settings": {"color_theme": "green", "brightness": []}},
                        {"action": "switch_app", "app_id": []}):
            before = self.state.get_all()
            with self.assertRaises(ValueError):
                server._handle_ws_message(message, self.providers, self.fetcher, Mock())
            self.assertEqual(self.state.get_all(), before)
        self.fetcher.force_refresh.assert_not_called()

    def test_valid_existing_form_shapes(self):
        for url, payload in (("/api/layout", {"layout": "single", "slots": ["custom"]}),
                             ("/api/source/custom/config", {"title": "Test", "rows": [{"left": "A", "right": "B"}]}),
                             ("/api/source/weather/config", {"latitude": "51.5", "longitude": "-0.1", "units": "metric"}),
                             ("/api/source/mock/config", {"preset": "cycle", "cycle_presets": ["overview", "train"], "refresh_interval_sec": 20}),
                             ("/api/settings", {"brightness": 0.5, "color_theme": "green", "animations_enabled": False})):
            response = self.client.post(url, json=payload)
            self.assertEqual(response.status_code, 200, (url, response.get_json()))

    def test_malformed_json_does_not_write(self):
        before = self.state.get_all()
        response = self.client.post("/api/source/custom/config", data="{", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())
        self.assertEqual(self.state.get_all(), before)

    def test_ws_error_keeps_connection_usable(self):
        handlers = {}
        def route(sock, path):
            def register(fn):
                handlers[path] = fn
                return fn
            return register
        with patch("flask_sock.Sock.route", route):
            server.create_app(self.providers, self.fetcher)
        ws = Mock()
        ws.receive.side_effect = ["[]", '{"action":"get_state"}', None]
        before = self.state.get_all()
        handlers["/ws"](ws)
        messages = [json.loads(call.args[0]) for call in ws.send.call_args_list]
        self.assertEqual([m["type"] for m in messages], ["state", "error", "state"])
        self.assertEqual(self.state.get_all(), before)


if __name__ == "__main__":
    unittest.main()
