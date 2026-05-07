"""
日程 Provider。
支持 mock（内置假数据）和 ical（iCal URL，如 Google/Apple Calendar）。
"""
import time
import datetime
import logging
import requests
from typing import List, Tuple
from providers.base import BaseProvider
from board.content import BoardContent, BoardRow

log = logging.getLogger(__name__)


class CalendarProvider(BaseProvider):

    provider_id = "calendar"
    display_name = "Calendar"
    default_refresh_interval = 300  # 5分钟

    def get_config_schema(self):
        return {
            "ical_url":      {"type": "string", "label": "iCal URL（Google/Apple日历）",
                              "default": ""},
            "lookahead_days": {"type": "number", "label": "显示未来几天",
                               "default": 3},
        }

    def fetch(self) -> BoardContent:
        ical_url = self.config.get("ical_url", "")
        if not ical_url:
            return self._mock_content()
        return self._fetch_ical(ical_url)

    # ------------------------------------------------------------------
    # iCal
    # ------------------------------------------------------------------

    def _fetch_ical(self, url: str) -> BoardContent:
        try:
            from icalendar import Calendar
        except ImportError:
            log.error("icalendar package not installed, run: pip install icalendar")
            return self._mock_content()

        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        cal = Calendar.from_ical(resp.content)

        lookahead = int(self.config.get("lookahead_days", 3))
        today = datetime.date.today()
        end_date = today + datetime.timedelta(days=lookahead)

        events: List[Tuple[datetime.datetime, str, str]] = []
        for component in cal.walk():
            if component.name != "VEVENT":
                continue
            dtstart = component.get("DTSTART")
            if dtstart is None:
                continue
            dt = dtstart.dt
            if isinstance(dt, datetime.datetime):
                event_date = dt.date()
                time_str = dt.strftime("%H:%M")
            else:
                event_date = dt
                time_str = "All day"

            if today <= event_date <= end_date:
                summary = str(component.get("SUMMARY", ""))
                # 时长
                dtend = component.get("DTEND")
                dur_str = ""
                if dtend:
                    end_dt = dtend.dt
                    if isinstance(end_dt, datetime.datetime) and isinstance(dt, datetime.datetime):
                        delta = end_dt - dt
                        mins = int(delta.total_seconds() / 60)
                        if mins < 60:
                            dur_str = f"{mins}min"
                        else:
                            dur_str = f"{mins // 60}hr"
                events.append((event_date, time_str, summary, dur_str))

        events.sort(key=lambda e: (e[0], e[1]))

        rows = []
        current_day = None
        for event_date, time_str, summary, dur in events:
            if event_date != current_day:
                if current_day is not None:
                    rows.append(BoardRow(""))  # 空行分隔
                current_day = event_date
                is_today = (event_date == today)
                day_label = "Today" if is_today else event_date.strftime("%A")
                event_count = sum(1 for e in events if e[0] == event_date)
                if not is_today:
                    rows.append(BoardRow(day_label, f"{event_count} events",
                                         left_color="dim", right_color="dim"))
            color = "amber" if event_date == today else "dim"
            hl = (event_date == today and not rows)
            rows.append(BoardRow(f"{time_str}  {summary}", dur,
                                  left_color=color, right_color=color,
                                  highlight=hl))

        today_count = sum(1 for e in events if e[0] == today)
        next_event = next((e for e in events if e[0] == today), None)
        status_text = f"Next: {next_event[1]}" if next_event else "No events"

        return BoardContent(
            header_left=today.strftime("%a").upper(),
            header_right=today.strftime("%d %b"),
            title="Today's Schedule",
            subtitle=f"{today_count} events" if today_count else "No events today",
            rows=rows,
            footer="Calendar",
            status_text=status_text,
            status_color="green" if next_event else "dim",
            provider_id=self.provider_id,
            expires_at=time.time() + 300,
        )

    # ------------------------------------------------------------------
    # Mock
    # ------------------------------------------------------------------

    def _mock_content(self) -> BoardContent:
        today = datetime.date.today()
        return BoardContent(
            header_left=today.strftime("%a").upper(),
            header_right=today.strftime("%d %b"),
            title="Today's Schedule",
            subtitle="3 events",
            rows=[
                BoardRow("09:00  Team standup",   "30min", highlight=True),
                BoardRow("14:00  Dentist",         "1hr"),
                BoardRow("19:30  Dinner - Marks",  "2hr"),
                BoardRow(""),
                BoardRow("Tomorrow",               "2 events",
                         left_color="dim", right_color="dim"),
                BoardRow("10:00  Code review",     "1hr",
                         left_color="dim", right_color="dim"),
                BoardRow("16:00  Weekly sync",     "45min",
                         left_color="dim", right_color="dim"),
            ],
            footer="Google Calendar (mock)",
            status_text="Next: 09:00",
            status_color="green",
            provider_id=self.provider_id,
        )


if __name__ == "__main__":
    p = CalendarProvider(config={})
    c = p.fetch()
    print(f"title={c.title!r}, rows={len(c.rows)}, status={c.status_text!r}")
