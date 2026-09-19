#!/usr/bin/env python3
"""Offline typography and board-layout checks for the 600x1024 display."""
import datetime
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "piboard"))

import pygame  # noqa: E402

from bindings.calendar_to_uk import CalendarToUKBinding  # noqa: E402
from board.board_renderer import BoardRenderer  # noqa: E402
from board.content import BoardContent, BoardRow  # noqa: E402
from board.dot_font import (  # noqa: E402
    FontSize, _FONT_5X7, _FONT_7X9, _get_bitmap, fit_text, measure_text,
    render_text,
)
from config import COLORS  # noqa: E402
from providers.mock import MockProvider  # noqa: E402
from providers.calendar_bridge import CalendarSourceBridge  # noqa: E402
from providers.calendar_provider import CalendarProvider  # noqa: E402
from sources.calendar import CalendarSchedule  # noqa: E402


def check_bitmap_alignment() -> None:
    for char in ("?", "!", "a", "&"):
        bitmap = _get_bitmap(char, FontSize.LARGE)
        assert len(bitmap) == 9
        assert bitmap[0] == bitmap[-1] == 0
        assert bitmap[1:8] == [row << 1 for row in _FONT_5X7[char]]
    assert _FONT_5X7["3"][0] == _FONT_5X7["3"][-1]
    assert _FONT_7X9["3"][0] == _FONT_7X9["3"][-1]


def check_text_widths() -> None:
    surface = pygame.Surface((1400, 100))
    for size in (FontSize.SMALL, FontSize.MEDIUM,
                 FontSize.LARGE, FontSize.XLARGE):
        for value in ("RAIL 01:37 CN", "BIRMINGHAM", "23\u00b0C", "日程"):
            width, _ = measure_text(value, size)
            right = render_text(surface, value, 8, 8, size, COLORS["amber"])
            assert right == 8 + width, (size, value)
            fitted = fit_text(value, size, max(1, width - 20))
            assert measure_text(fitted, size)[0] <= max(1, width - 20)


def check_calendar_empty_state() -> None:
    assert CalendarProvider().get_config_schema()["ical_url"]["secret"] is True
    today = datetime.date(2026, 9, 20)
    raw = CalendarSchedule(
        today=today, events=[], fetched_at=1_790_000_000,
        source_label="Google Calendar (mock)",
    )
    content = CalendarToUKBinding().transform(raw)
    assert [row.left for row in content.rows] == ["UPCOMING"]
    assert content.ticker is None
    assert content.footer == raw.source_label
    assert content.status_text.startswith("UPDATED ")
    overview = MockProvider(config={})
    calendar = overview._overview_calendar_from_content(
        content, datetime.datetime.now())
    assert calendar["next_label"] == ""
    weather = {
        "available": True, "temperature": "20C",
        "description": "CLEAR", "detail": "DRY",
    }
    assert not overview._overview_hero(calendar, weather)[0].startswith("NEXT")

    mock_calendar = CalendarSourceBridge(config={"ical_url": ""})
    mock_calendar._cached_content = mock_calendar.fetch()
    overview.set_linked_calendar_provider(mock_calendar)
    calendar_state = overview._overview_calendar(datetime.datetime.now())
    assert calendar_state["state"] == "MOCK"


def check_portrait_render() -> None:
    renderer = BoardRenderer(COLORS)
    surface = pygame.Surface((600, 1024))
    content = BoardContent(
        header_left="RAIL", header_right="01:37 CN",
        title="BIRMINGHAM INTERNATIONAL",
        subtitle="NEXT 18:35 UK - BOARDING",
        page_label="PLATFORM 12",
        rows=[BoardRow("BIRMINGHAM INTERNATIONAL", "DELAYED 25 MIN")
              for _ in range(10)],
        footer="LIVE DEPARTURES FROM STATION",
        status_text="SERVICE INFORMATION AVAILABLE",
        ticker="Live train data updated regularly.",
        template="train",
    )
    row_h = renderer.get_row_height(1024, content, 600)
    assert 38 < row_h <= 50
    renderer.render(surface, content, ticker_page=0)
    assert surface.get_at((0, 0))[:3] != COLORS["amber"]


def main() -> int:
    pygame.init()
    try:
        for name, check in (
            ("bitmap alignment", check_bitmap_alignment),
            ("text widths", check_text_widths),
            ("calendar empty state", check_calendar_empty_state),
            ("portrait render", check_portrait_render),
        ):
            check()
            print(f"PASS {name}")
    finally:
        pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
