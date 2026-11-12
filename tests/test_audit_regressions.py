"""Offline regressions for the 2026-11 project audit.

Run: python3 -m unittest discover -s tests -p 'test_*.py'
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'piboard'))

from data.fetcher import DataFetcher
from providers.custom import CustomProvider
from state import AppState, _default_state, _normalize_source_configs


class StateRecoveryTests(unittest.TestCase):
    def setUp(self):
        # An isolated instance; never touch the runtime singleton or state.json.
        self.state = object.__new__(AppState)
        self.state._init()

    def load(self, payload):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            path.write_text(json.dumps(payload))
            self.state.load(str(path))

    def test_weather_migration_preserves_manual_city(self):
        for version in (None, 1):
            with self.subTest(version=version):
                payload = {'providers_config': {'weather': {'city': 'Paris'}}}
                if version:
                    payload = {'schema_version': 1, 'source_configs': payload['providers_config']}
                self.load(payload)
                self.assertEqual(self.state.get_source_config('weather')['location_mode'], 'manual')

    def test_weather_legacy_london_policy_and_explicit_mode(self):
        for weather, mode, city in [
            ({'city': 'London'}, 'auto', ''),
            ({'city': 'Paris'}, 'manual', 'Paris'),
            ({'city': 'London', 'location_mode': 'manual'}, 'manual', 'London'),
        ]:
            cfg = {'weather': weather}
            _normalize_source_configs(cfg)
            self.assertEqual((cfg['weather']['location_mode'], cfg['weather']['city']), (mode, city))

    def test_invalid_load_is_atomic(self):
        before = self.state.get_all()
        for invalid in ({'apps': []}, {'apps': {'uk_station': None}},
                        {'apps': {'uk_station': {'slots': [None]}}},
                        {'source_configs': []}, {'device_settings': None}):
            self.load({'schema_version': 1, 'current_app': 'system_status', **invalid})
            self.assertEqual(self.state.get_all(), before)

    def test_partial_app_restores_missing_defaults(self):
        self.load({'schema_version': 1, 'apps': {'uk_station': {'layout': 'dual'}}})
        cfg = self.state.get_app_state('uk_station')
        self.assertEqual(cfg['layout'], 'dual')
        self.assertEqual(cfg['slots'], ['mock'])
        self.assertEqual(cfg['app_settings'], _default_state()['apps']['uk_station']['app_settings'])

    def test_save_filename_without_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            old = os.getcwd()
            try:
                os.chdir(directory)
                self.state.save('state.json')
                self.assertEqual(json.loads(Path('state.json').read_text())['schema_version'], 1)
            finally:
                os.chdir(old)


class FetcherTests(unittest.TestCase):
    def test_slow_source_coalesces_refreshes_and_uses_latest_config(self):
        started, release = threading.Event(), threading.Event()
        values = []
        class Slow(CustomProvider):
            def fetch(self):
                values.append(self.config.get('title'))
                started.set()
                if len(values) == 1:
                    if not release.wait(5):
                        raise TimeoutError('test did not release fetch')
                return super().fetch()
        p = Slow({'title': 'old'})
        fetcher = DataFetcher()
        fetcher.register(p)
        try:
            first = fetcher.force_refresh('custom')
            self.assertTrue(started.wait(2))
            p.update_config({'title': 'new'})
            pending = [fetcher.force_refresh('custom') for _ in range(100)]
            self.assertTrue(all(f is pending[0] for f in pending))
            self.assertIsNot(first, pending[0])
            self.assertEqual(values, ['old'])
            release.set()
            self.assertTrue(first.result(3))
            self.assertTrue(pending[0].result(3))
            self.assertEqual(values, ['old', 'new'])
            self.assertEqual(p.get_content().title, 'new')
        finally:
            release.set()
            fetcher.stop()

    def test_stop_cancels_pending_and_rejects_new_work(self):
        started, release = threading.Event(), threading.Event()
        class Slow(CustomProvider):
            def fetch(self):
                started.set()
                release.wait(5)
                return super().fetch()
        fetcher = DataFetcher()
        fetcher.register(Slow())
        try:
            first = fetcher.force_refresh('custom')
            self.assertTrue(started.wait(2))
            pending = fetcher.force_refresh('custom')
            fetcher.stop()
            self.assertTrue(pending.cancelled())
            self.assertIsNone(fetcher.force_refresh('custom'))
            release.set()
            self.assertTrue(first.result(3))
        finally:
            release.set()
            fetcher.stop()

    def test_scheduler_stops_before_executor_shutdown(self):
        fetcher = DataFetcher()
        fetcher.start()
        fetcher.stop()
        self.assertFalse(fetcher._thread.is_alive())


class OverviewTests(unittest.TestCase):
    def test_unavailable_and_expired_train_are_not_live(self):
        import datetime
        from providers.mock import MockProvider
        from providers.train_bridge import TrainSourceBridge
        from bindings.train_to_uk import TrainToUKBinding
        from sources.train import TrainBoardData
        now = datetime.datetime.now().timestamp()
        provider = TrainSourceBridge({'data_source': 'huxley2'})
        overview = MockProvider()
        overview.set_linked_train_provider(provider)
        for error, timestamp, expected in [('HTTP 500', now, 'WAIT'), ('', now - 120, 'STALE')]:
            raw = TrainBoardData('Test', 'TST', [], [], timestamp, mode='departures', error=error)
            provider._cached_content = TrainToUKBinding().transform(raw)
            with patch.object(overview, '_source_config', return_value={'data_source': 'huxley2'}):
                self.assertEqual(overview._overview_rail()['state'], expected)

    def test_live_calendar_cache_expires(self):
        import datetime
        from providers.mock import MockProvider
        from providers.calendar_bridge import CalendarSourceBridge
        from bindings.calendar_to_uk import CalendarToUKBinding
        from sources.calendar import CalendarSchedule
        now = datetime.datetime.now()
        timestamp = now.timestamp() - 301
        provider = CalendarSourceBridge({'ical_url': 'https://example.invalid/calendar.ics'})
        content = CalendarToUKBinding().transform(CalendarSchedule(now.date(), [], timestamp, 'iCal live'))
        overview = MockProvider()
        overview.set_linked_calendar_provider(provider)
        self.assertEqual(overview._overview_calendar_from_content(content, now)['state'], 'STALE')
        self.assertEqual(overview._content_fetched_at(content, provider), timestamp)

    def test_unlinked_train_demo_is_labelled(self):
        from providers.mock import MockProvider
        content = MockProvider({'preset': 'train'}).fetch()
        self.assertEqual(content.status_text, 'DEMO')
        self.assertIn('mock', content.footer)


class AnimationWakeupTests(unittest.TestCase):
    def test_animated_carousel_has_deadline_without_ticker_or_clock(self):
        from layouts.carousel import CarouselLayout
        from config import COLORS
        layout = CarouselLayout(COLORS, animations_enabled=True, interval_ms=10000)
        layout._last_switch = 100
        providers = [CustomProvider(), CustomProvider()]
        self.assertEqual(layout.next_render_ms(providers, 200), 10100)

    def test_updated_row_count_reconfigures_paging(self):
        import pygame
        from config import COLORS
        from layouts.single import SingleLayout
        from layouts.dual import DualLayout
        from layouts.carousel import CarouselLayout
        pygame.init()
        try:
            for cls in (SingleLayout, DualLayout, CarouselLayout):
                with self.subTest(layout=cls.__name__):
                    p = CustomProvider({'rows': ['one']})
                    p.fetch()
                    layout = cls(COLORS)
                    surface = pygame.Surface((600, 1024))
                    layout.render(surface, [p])
                    p.update_config({'rows': ['row'] * 30})
                    p.fetch()
                    layout.render(surface, [p])
                    anim = layout._anims[0] if hasattr(layout, '_anims') else layout._anim
                    self.assertEqual(anim.page_flip._rows_count, 30)
                    self.assertGreater(anim.page_flip._total_pages, 1)
        finally:
            pygame.quit()

    def test_rows_wake_host_before_page_flip_begins(self):
        from apps.uk_station.app import UKStationApp
        from layouts.single import SingleLayout
        from config import COLORS
        p = CustomProvider({'rows': ['row'] * 30})
        p.fetch()
        app = UKStationApp({'single': SingleLayout(COLORS)}, {'custom': p},
                           'single', ['custom'], {'animations_enabled': True})
        page = app._current_layout._anim.page_flip
        page.configure(30, 100, 30)
        self.assertFalse(app.is_animating())
        self.assertEqual(app.next_render_ms(0), page._last_page_time + page.interval_ms + 1)


class WebAndDisplayTests(unittest.TestCase):
    def test_server_runs_with_concurrent_requests(self):
        from main import start_web_server
        fetcher = DataFetcher()
        try:
            with patch('flask.Flask.run') as run:
                start_web_server({}, fetcher)
            self.assertTrue(run.call_args.kwargs['threaded'])
        finally:
            fetcher.stop()

    def test_websocket_waits_for_messages_without_idle_disconnect(self):
        from web.server import create_app
        handlers = {}
        def route(sock, path):
            def register(fn):
                handlers[path] = fn
                return fn
            return register
        fetcher = DataFetcher()
        try:
            with patch('flask_sock.Sock.route', route):
                create_app({}, fetcher)
            class Connection:
                def send(self, message):
                    pass
                # A browser can remain idle; no arbitrary application timeout.
                received = False
                def receive(self):
                    self.received = True
                    return None
            connection = Connection()
            with patch('web.server.log.warning') as warning:
                handlers['/ws'](connection)
                self.assertTrue(connection.received)
                warning.assert_not_called()
        finally:
            fetcher.stop()

    def test_status_layout_uses_logical_surface(self):
        import pygame
        from apps.system_status.app import SystemStatusApp
        pygame.init()
        try:
            pygame.display.set_mode((1024, 600))
            logical = pygame.Surface((600, 1024))
            app = SystemStatusApp()
            app.on_activate()
            app.render(logical, 0)
            self.assertEqual(app._surface_size, (600, 1024))
            for surface, (x, y) in app._surfaces:
                self.assertEqual(surface.get_size(), logical.get_size())
                self.assertEqual((x, y), (0, 0))
            landscape = pygame.Surface((1024, 600))
            app.render(landscape, 0)
            self.assertEqual(app._surface_size, landscape.get_size())
        finally:
            pygame.quit()


if __name__ == '__main__':
    unittest.main()
