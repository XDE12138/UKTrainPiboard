#!/usr/bin/env python3
"""Render v0.1.1 acceptance screenshots offscreen on the Pi.

This is a release-evidence helper, not a runtime feature. It renders the five
existing v0.1.1 pages with safe example configs and writes PNG files.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from board.board_renderer import BoardRenderer  # noqa: E402
from config import COLORS, PORTRAIT_HEIGHT, PORTRAIT_WIDTH  # noqa: E402
from providers.calendar_bridge import CalendarSourceBridge  # noqa: E402
from providers.custom import CustomProvider  # noqa: E402
from providers.mock import MockProvider  # noqa: E402
from providers.train_bridge import TrainSourceBridge  # noqa: E402
from providers.weather_bridge import WeatherSourceBridge  # noqa: E402


SAFE_CONFIGS = {
    "mock": {
        "preset": "overview",
        "cycle_presets": ["overview", "train", "weather", "calendar"],
        "refresh_interval_sec": 20,
    },
    "train": {
        "station_crs": "KGX",
        "destination_crs": "",
        "api_key": "",
        "data_source": "mock",
    },
    "weather": {
        "location_mode": "manual",
        "city": "London",
        "latitude": "",
        "longitude": "",
        "api_key": "",
        "units": "metric",
    },
    "calendar": {
        "ical_url": "",
        "lookahead_days": 3,
    },
    "custom": {
        "header_left": "",
        "header_right": "",
        "title": "PiBoard",
        "subtitle": "Custom Display",
        "rows": [],
        "footer": "",
        "status_text": "OK",
        "status_color": "green",
        "ticker": "",
    },
}


def _provider_content(provider):
    content = provider.fetch()
    provider._cached_content = content
    return content


def render_page(renderer, content, out_path: Path):
    surface = pygame.Surface((PORTRAIT_WIDTH, PORTRAIT_HEIGHT))
    renderer.render(surface, content, ticker_offset=0, rows_scroll_offset=0)
    pygame.image.save(surface, str(out_path))
    print(out_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out-dir",
        default=str(APP_ROOT / "review_artifacts" / "pi-acceptance-v0.1.1"),
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pygame.display.init()
    pygame.display.set_mode((1, 1))

    train = TrainSourceBridge(config=dict(SAFE_CONFIGS["train"]))
    weather = WeatherSourceBridge(config=dict(SAFE_CONFIGS["weather"]))
    calendar = CalendarSourceBridge(config=dict(SAFE_CONFIGS["calendar"]))
    custom = CustomProvider(config=dict(SAFE_CONFIGS["custom"]))
    mock = MockProvider(config=dict(SAFE_CONFIGS["mock"]))

    train_content = _provider_content(train)
    weather_content = _provider_content(weather)
    calendar_content = _provider_content(calendar)
    custom_content = _provider_content(custom)

    mock.set_linked_train_provider(train)
    mock.set_linked_weather_provider(weather)
    mock.set_linked_calendar_provider(calendar)
    overview_content = _provider_content(mock)

    pages = {
        "overview": overview_content,
        "train": train_content,
        "weather": weather_content,
        "calendar": calendar_content,
        "custom": custom_content,
    }

    renderer = BoardRenderer(COLORS)
    for name, content in pages.items():
        render_page(renderer, content, out_dir / f"{name}.png")

    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
