"""Offline board specimens and an isolated, in-memory console for visual QA.

Run with --out-dir PATH to render boards, or --serve to preview the console.
Never loads or saves the user's state.json and never calls a live provider.
"""
from __future__ import annotations

import argparse
from concurrent.futures import Future
from copy import deepcopy
import datetime as dt
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "piboard"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
from bindings.calendar_to_uk import CalendarToUKBinding
from bindings.train_to_uk import TrainToUKBinding
from bindings.weather_to_uk import WeatherToUKBinding
from board.board_renderer import BoardRenderer
from board.content import BoardContent, BoardRow
from board.dot_font import FontSize, render_text
from config import COLORS, COLOR_THEMES
from sources.calendar import CalendarEvent, CalendarSchedule, CalendarSource
from sources.train import TrainSource, TrainBoardData, TrainDeparture
from sources.weather import WeatherSource


def specimens():
    now = dt.datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    stamp = now.timestamp()
    train = TrainToUKBinding().transform(TrainSource({})._mock_data())
    weather = WeatherToUKBinding().transform(WeatherSource({})._mock_data())
    weather.footer = "WEATHER DEMO"
    calendar = CalendarToUKBinding().transform(CalendarSource({})._mock_data())
    mixed = CalendarSchedule(now.date(), [
        CalendarEvent(now.date(), now + dt.timedelta(hours=i),
                      f"{10+i:02}:00", title, "30 MIN", end_time_str=f"{10+i:02}:30")
        for i, title in enumerate(["Morning review", "项目进度讨论", "Design & delivery review"], 1)
    ], stamp, "CALENDAR DEMO")
    live_shape = TrainBoardData("Birmingham New Street", "BHM", [
        TrainDeparture(name, f"11:{i:02}", status, str(i+1), "Example operator", [])
        for i, (name, status) in enumerate([
            ("Manchester Piccadilly", "On time"), ("Birmingham International", "Delayed"),
            ("Liverpool Lime Street", "On time"), ("Lichfield Trent Valley", "11:20"),
            ("Worcester Foregate Street", "On time"), ("Nottingham", "On time")])
    ], [], stamp, mode="departures")
    rail = TrainToUKBinding().transform(live_shape)
    rail.footer = "RAIL FIXTURE / NOT LIVE"
    error = TrainToUKBinding().transform(TrainBoardData(
        "Birmingham New Street", "BHM", [], [], stamp,
        mode="departures", error="HTTP 500"))
    custom = BoardContent(
        header_left="NOTICE", header_right="PIBOARD", title="WELCOME",
        subtitle="A quiet place for the day ahead",
        rows=[BoardRow("DESK", "READY", highlight=True),
              BoardRow("项目进度 Project review", "11:30"),
              BoardRow("Long platform announcement for the next service", "12:45 UK")],
        footer="CUSTOM TEXT", status_text="MANUAL", status_color="amber",
        ticker="Platform information and 项目进度说明 are shown without distorted text.",
        template="info")
    from providers.mock import MockProvider
    overview = MockProvider({"preset": "overview"}).fetch()
    return {
        "overview": overview, "train-demo": train, "train-departures": rail,
        "train-empty": TrainToUKBinding().transform(TrainBoardData(
            "Birmingham New Street", "BHM", [], [], stamp, mode="departures")),
        "train-error": error, "weather": weather, "calendar": calendar,
        "calendar-mixed": CalendarToUKBinding().transform(mixed),
        "calendar-empty": CalendarToUKBinding().transform(
            CalendarSchedule(now.date(), [], stamp, "CALENDAR DEMO")),
        "custom": custom, "custom-empty": BoardContent(provider_id="custom"),
        "loading": BoardContent(title="CALENDAR", subtitle="Loading...",
                                 status_text="WAIT", status_color="orange"),
        "dense": BoardContent(title="DEPARTURES", subtitle="Calling at:",
                              rows=[BoardRow(f"Station {i:02} 项目", "11:30 UK")
                                    for i in range(30)], footer="RENDER FIXTURE"),
    }


def export(out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    pages = specimens()
    renderer = BoardRenderer(COLORS)
    for size in [(600, 1024), (1024, 600), (600, 512), (512, 600)]:
        for name, content in pages.items():
            surface = pygame.Surface(size)
            renderer.render(surface, content, ticker_page=0)
            pygame.image.save(surface, str(out_dir / f"{name}-{size[0]}x{size[1]}.png"))
    from providers.custom import CustomProvider
    from layouts.single import SingleLayout
    from layouts.dual import DualLayout
    from layouts.carousel import CarouselLayout
    providers = []
    for name in ['calendar-mixed', 'train-departures', 'weather']:
        provider = CustomProvider({})
        provider._cached_content = pages[name]
        providers.append(provider)
    for size in [(600,1024),(1024,600)]:
        for cls in [SingleLayout,DualLayout,CarouselLayout]:
            for enabled in [False,True]:
                surface = pygame.Surface(size)
                cls(COLORS,animations_enabled=enabled).render(surface,providers)
                pygame.image.save(surface,str(out_dir/f"layout-{cls.layout_id}-{enabled}-{size[0]}x{size[1]}.png"))
    for name, colors in COLOR_THEMES.items():
        surface = pygame.Surface((600,1024))
        BoardRenderer(colors).render(surface,pages['calendar-mixed'],ticker_page=0)
        pygame.image.save(surface,str(out_dir/f"theme-{name}.png"))
    from apps.system_status.app import SystemStatusApp
    for size in [(600, 1024), (1024, 600)]:
        surface = pygame.Surface(size)
        SystemStatusApp().render(surface, 0)
        pygame.image.save(surface, str(out_dir / f"system-{size[0]}x{size[1]}.png"))
    surface = pygame.Surface((1400, 480))
    surface.fill((8, 8, 8))
    y = 12
    for size in [FontSize.SMALL, FontSize.MEDIUM, FontSize.LARGE, FontSize.XLARGE]:
        render_text(surface, "ABC 0123 北京 项目 • – ’", 12, y, size, COLORS["amber"])
        y += 110
    pygame.image.save(surface, str(out_dir / "typography.png"))
    pygame.quit()
    from PIL import Image, ImageDraw
    for suffix, label, thumb in [('600x1024','portrait',(192,330)),
                                 ('600x512','half',(240,205)),
                                 ('1024x600','landscape',(256,150))]:
        paths = sorted(out_dir.glob(f'*-{suffix}.png'))
        cell_w,cell_h = thumb[0]+12,thumb[1]+32
        sheet = Image.new('RGB',(5*cell_w,((len(paths)+4)//5)*cell_h),(32,32,32))
        draw = ImageDraw.Draw(sheet)
        for i,path in enumerate(paths):
            image = Image.open(path); image.thumbnail(thumb)
            x,y=(i%5)*cell_w,(i//5)*cell_h
            sheet.paste(image,(x,y+24)); draw.text((x+4,y+4),path.stem.replace('-'+suffix,''),fill='white')
        sheet.save(out_dir/f'{label}-contact.png')
    print(f"Exported {len(list(out_dir.glob('*.png')))} offline specimens/contact sheets to {out_dir}")


def serve(port):
    from main import build_providers
    from state import app_state
    from web.server import create_app
    app_state.load(str(ROOT / "piboard/data/state.example.json"))
    app_state.update_source_config("weather", {"location_mode": "manual", "city": "London"})
    providers = build_providers()
    pages = specimens()
    for sid, name in [("train", "train-demo"), ("weather", "weather"),
                      ("calendar", "calendar-mixed"), ("custom", "custom")]:
        providers[sid]._cached_content = deepcopy(pages[name])

    class OfflineFetcher:
        def force_refresh(self, sid):
            result = Future()
            if sid == "custom":
                providers[sid].fetch()
            result.set_result(True)
            return result

    create_app(providers, OfflineFetcher()).run(
        host="127.0.0.1", port=port, threaded=True, use_reloader=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=8081)
    args = parser.parse_args()
    if args.serve:
        serve(args.port)
    elif args.out_dir:
        export(args.out_dir)
    else:
        parser.error("choose --out-dir or --serve")
