"""Mock Provider：内置预设 BoardContent，无需任何 API Key，开发调试用。"""
import copy
import datetime as _dt
import time as _time

from providers.base import BaseProvider
from board.content import BoardContent, BoardRow
from bindings.overview_to_uk import (
    OverviewAction,
    OverviewBoardData,
    OverviewSummary,
    OverviewToUKBinding,
)


class MockProvider(BaseProvider):

    provider_id = "mock"
    display_name = "Mock (Demo)"
    default_refresh_interval = 60  # low-power overview refresh / cycle cadence
    _preset_order = ("overview", "train", "weather", "calendar")
    _preset_labels = {
        "overview": "概览",
        "train": "列车",
        "weather": "天气",
        "calendar": "日程",
    }

    def __init__(self, config=None):
        super().__init__(config)
        self._overview_binding = OverviewToUKBinding()
        self._index = 0
        self._linked_weather_provider = None
        self._linked_calendar_provider = None
        self._linked_train_provider = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self) -> BoardContent:
        preset = self.config.get("preset", "overview")
        if preset == "cycle":
            cycle_presets = self._cycle_presets()
            preset = cycle_presets[self._index % len(cycle_presets)]
            self._index += 1
        content = self._get_preset(preset)
        content.provider_id = f"mock:{preset}"
        self._cached_content = content
        return content

    def update_config(self, new_config):
        old_preset = self.config.get("preset", "overview")
        old_cycle = tuple(self._cycle_presets())
        super().update_config(new_config)
        new_cycle = tuple(self._cycle_presets())
        if self.config.get("preset", "overview") != old_preset or new_cycle != old_cycle:
            self._index = 0

    def get_refresh_interval(self) -> float:
        return self._coerce_refresh_interval(
            self.config.get("refresh_interval_sec",
                            self.default_refresh_interval)
        )

    def set_linked_weather_provider(self, provider):
        self._linked_weather_provider = provider

    def set_linked_calendar_provider(self, provider):
        self._linked_calendar_provider = provider

    def set_linked_train_provider(self, provider):
        self._linked_train_provider = provider

    def get_config_schema(self):
        return {
            "preset": {
                "type": "select",
                "label": "预设内容",
                "options": ["overview", "train", "weather", "calendar", "cycle"],
                "default": "overview",
            },
            "cycle_presets": {
                "type": "multi_select",
                "label": "低功耗轮播页面",
                "options": [
                    {"value": key, "label": self._preset_labels[key]}
                    for key in self._preset_order
                ],
                "default": list(self._preset_order),
            },
            "refresh_interval_sec": {
                "type": "number",
                "label": "刷新/轮播间隔（秒）",
                "default": self.default_refresh_interval,
            }
        }

    # ------------------------------------------------------------------
    # Presets
    # ------------------------------------------------------------------

    def _get_preset(self, preset: str) -> BoardContent:
        if preset == "train":
            return self._train_preset()
        if preset == "weather":
            return self._weather_preset()
        if preset == "calendar":
            return self._calendar_preset()
        return self._overview_preset()

    @staticmethod
    def _coerce_refresh_interval(value) -> float:
        try:
            interval = float(value)
        except (TypeError, ValueError):
            interval = MockProvider.default_refresh_interval
        return max(10.0, min(3600.0, interval))

    def _cycle_presets(self) -> tuple:
        raw = self.config.get("cycle_presets", self._preset_order)
        if isinstance(raw, str):
            raw = [raw]
        allowed = set(self._preset_order)
        presets = tuple(p for p in raw if p in allowed)
        return presets or self._preset_order

    def _overview_preset(self) -> BoardContent:
        now = _dt.datetime.now()
        weather = self._overview_weather(now)
        calendar = self._overview_calendar(now)
        rail = self._overview_rail()

        actions = []
        if calendar["available"]:
            actions.append(self._overview_calendar_action(calendar))
        else:
            actions.append(OverviewAction(
                "CAL", "NOW", "CALENDAR CACHE",
                calendar["state"], calendar["state_color"],
                detail=calendar["detail"],
            ))

        if weather["available"]:
            actions.append(OverviewAction(
                "WX", "NOW", weather["description"],
                weather["temperature"], weather["state_color"],
                detail=weather["detail"],
            ))
        else:
            actions.append(OverviewAction(
                "WX", "NOW", "WEATHER CACHE",
                weather["state"], weather["state_color"],
                detail=weather["detail"],
            ))

        if rail["state"] != "LIVE":
            actions.append(OverviewAction(
                "RAIL", "SETUP", "TRAIN DATA SOURCE",
                rail["state"], rail["state_color"],
                detail=rail["detail"],
            ))

        summaries = [
            OverviewSummary(
                "WEATHER", weather["summary"], weather["right"],
                "dim", weather["state_color"],
            ),
            OverviewSummary(
                "CAL", calendar["summary"], calendar["right"],
                "dim", calendar["state_color"],
            ),
            OverviewSummary(
                "RAIL", rail["summary"], rail["right"],
                "dim", rail["state_color"],
            ),
            OverviewSummary(
                "SYNC", self._overview_sync_value(weather, calendar),
                f"UPD {now:%H:%M}", "dim",
                self._overview_status_color(weather, calendar),
            ),
        ]

        hero_primary, hero_secondary = self._overview_hero(calendar, weather)
        source_times = [
            ts for ts in (
                weather.get("fetched_at") or 0,
                calendar.get("fetched_at") or 0,
            )
            if ts
        ]
        fetched_at = max(source_times) if source_times else now.timestamp()
        status_text, status_color = self._overview_status(weather, calendar)
        location = self._overview_location(weather)

        raw = OverviewBoardData(
            now=now,
            location=location,
            hero_primary=hero_primary,
            hero_secondary=hero_secondary,
            actions=actions,
            summaries=summaries,
            footer="LIVE DATA" if status_text == "LIVE" else "LOCAL DATA",
            status_text=status_text,
            status_color=status_color,
            ticker=(
                f"CAL {calendar['state']} - WEATHER {weather['state']} - "
                f"RAIL {rail['state']} - UPDATED {now:%H:%M}"
            ),
            fetched_at=fetched_at,
        )
        return self._overview_binding.transform(raw)

    def _overview_calendar_action(self, calendar: dict) -> OverviewAction:
        event = calendar.get("next_event")
        if event is None and calendar.get("next_label"):
            return OverviewAction(
                "CAL",
                calendar.get("next_time", "CAL"),
                calendar.get("next_label", "CALENDAR EVENT"),
                calendar.get("next_duration", "") or "EVENT",
                "white" if calendar["state"] == "LIVE" else calendar["state_color"],
                detail=calendar.get("next_detail", "CALENDAR"),
            )
        if event is None:
            return OverviewAction(
                "CAL", "NOW", "NO EVENTS TODAY",
                calendar["state"], calendar["state_color"],
                detail=calendar["detail"],
            )

        duration = getattr(event, "dur_str", "") or "EVENT"
        detail = self._overview_calendar_detail(event)
        return OverviewAction(
            "CAL",
            self._overview_event_time(event),
            getattr(event, "summary", "") or "CALENDAR EVENT",
            duration,
            "white" if calendar["state"] == "LIVE" else calendar["state_color"],
            detail=detail,
        )

    def _overview_weather(self, now: _dt.datetime) -> dict:
        content = self._linked_content(self._linked_weather_provider)
        if content is not None:
            return self._overview_weather_from_content(content, now)

        raw = self._linked_source_data(self._linked_weather_provider)
        if raw is not None and hasattr(raw, "temperature"):
            state, state_color = self._freshness(
                getattr(raw, "fetched_at", 0), self._linked_weather_provider, now)
            forecast = list(getattr(raw, "forecast", []) or [])
            today = ""
            if forecast:
                _day, hi, lo = forecast[0]
                today = f"{hi}/{lo}"
            temp = f"{getattr(raw, 'temperature', '--')}{getattr(raw, 'unit_sym', '')}"
            desc = str(getattr(raw, "description", "WEATHER")).upper()
            return {
                "available": True,
                "state": state,
                "state_color": state_color,
                "city": str(getattr(raw, "city", "")).strip(),
                "temperature": temp,
                "description": desc,
                "detail": (
                    f"FEELS {getattr(raw, 'feels_like', '--')}"
                    f"{getattr(raw, 'unit_sym', '')} "
                    f"WIND {str(getattr(raw, 'wind_dir', '')).upper()} "
                    f"{str(getattr(raw, 'wind_speed_str', '')).upper()}"
                ).strip(),
                "summary": f"{temp} {desc}",
                "right": today or state,
                "fetched_at": getattr(raw, "fetched_at", 0),
            }

        return {
            "available": False,
            "state": "WAIT",
            "state_color": "orange",
            "city": self._weather_location_label(),
            "temperature": "--",
            "description": "WEATHER",
            "detail": "LIVE DATA NOT READY",
            "summary": "WAITING",
            "right": "CACHE",
            "fetched_at": 0,
        }

    def _overview_weather_from_content(self, content: BoardContent,
                                       now: _dt.datetime) -> dict:
        state, state_color = self._content_freshness(
            content, self._linked_weather_provider, now)
        title = str(getattr(content, "title", "") or "--")
        desc = str(getattr(content, "subtitle", "") or "WEATHER").upper()
        feels = self._row_right(content, "FEELS")
        wind = self._row_right(content, "WIND")
        today = self._row_right(content, "TODAY")
        detail_parts = []
        if feels:
            detail_parts.append(f"FEELS {feels}")
        if wind:
            detail_parts.append(f"WIND {wind}")
        detail = " ".join(detail_parts) or "WEATHER PAGE"
        return {
            "available": True,
            "state": state,
            "state_color": state_color,
            "city": str(getattr(content, "page_label", "")).split(" UPD ", 1)[0],
            "temperature": title,
            "description": desc,
            "detail": detail,
            "summary": f"{title} {desc}",
            "right": today or state,
            "fetched_at": self._content_fetched_at(content),
        }

    def _overview_calendar(self, now: _dt.datetime) -> dict:
        content = self._linked_content(self._linked_calendar_provider)
        if content is not None:
            return self._overview_calendar_from_content(content, now)

        raw = self._linked_source_data(self._linked_calendar_provider)
        if raw is not None and hasattr(raw, "events"):
            fetched_at = getattr(raw, "fetched_at", 0)
            state, state_color = self._freshness(
                fetched_at, self._linked_calendar_provider, now)
            events = sorted(
                list(getattr(raw, "events", []) or []),
                key=lambda e: (
                    getattr(e, "event_date", _dt.date.max),
                    _dt.datetime.min.time()
                    if getattr(e, "start_at", None) is None
                    else getattr(e, "start_at").time(),
                ),
            )
            today = getattr(raw, "today", now.date())
            today_count = sum(1 for e in events if getattr(e, "event_date", None) == today)
            next_event = self._overview_next_calendar_event(events, now)
            right = self._overview_event_time(next_event) if next_event else state
            return {
                "available": True,
                "state": state,
                "state_color": state_color,
                "next_event": next_event,
                "next_label": getattr(next_event, "summary", "") if next_event else "",
                "next_time": self._overview_event_time(next_event) if next_event else "",
                "next_duration": getattr(next_event, "dur_str", "") if next_event else "",
                "next_detail": self._overview_calendar_detail(next_event) if next_event else "",
                "today_count": today_count,
                "summary": f"{today_count} TODAY",
                "right": right,
                "detail": "GOOGLE ICAL",
                "fetched_at": fetched_at,
            }

        return {
            "available": False,
            "state": "WAIT",
            "state_color": "orange",
            "next_event": None,
            "today_count": 0,
            "summary": "WAITING",
            "right": "CACHE",
            "detail": "LIVE DATA NOT READY",
            "fetched_at": 0,
        }

    def _overview_calendar_from_content(self, content: BoardContent,
                                        now: _dt.datetime) -> dict:
        state, state_color = self._content_freshness(
            content, self._linked_calendar_provider, now)
        highlighted = self._highlighted_event_row(content)
        today_summary = self._calendar_today_summary(content)
        next_time = self._calendar_next_time(content, highlighted)
        next_label, next_detail = self._calendar_event_parts(highlighted.left) if highlighted else ("", "")
        next_duration = highlighted.right if highlighted else ""
        has_next = bool(highlighted and str(getattr(content, "status_text", "")).upper() != "NO EVENTS")
        return {
            "available": True,
            "state": state,
            "state_color": state_color,
            "next_event": None,
            "next_label": next_label if has_next else "",
            "next_time": next_time if has_next else "",
            "next_duration": next_duration if has_next else "",
            "next_detail": next_detail if has_next else "",
            "today_count": 0,
            "summary": today_summary or str(getattr(content, "subtitle", "") or "CALENDAR"),
            "right": next_time if has_next else state,
            "detail": "CALENDAR PAGE",
            "fetched_at": self._content_fetched_at(content),
        }

    def _overview_rail(self) -> dict:
        cfg = self._source_config("train")
        data_source = str(cfg.get("data_source", "mock")).upper()
        if data_source == "MOCK":
            return {
                "state": "MOCK",
                "state_color": "orange",
                "summary": "MOCK",
                "right": "SETUP",
                "detail": "TRAIN DETAIL PAGE USES DEMO",
            }
        content = self._linked_content(self._linked_train_provider)
        if content is None:
            return {
                "state": "WAIT",
                "state_color": "orange",
                "summary": data_source,
                "right": "CACHE",
                "detail": "LIVE DATA NOT READY",
            }
        return {
            "state": "LIVE",
            "state_color": "green",
            "summary": str(getattr(content, "title", "") or data_source).upper(),
            "right": str(getattr(content, "status_text", "") or "LIVE").upper(),
            "detail": str(getattr(content, "page_label", "") or "LIVE TRAIN DATA").upper(),
        }

    def _overview_hero(self, calendar: dict, weather: dict) -> tuple:
        event = calendar.get("next_event")
        if event is None and calendar.get("next_label"):
            secondary = calendar.get("next_label", "CALENDAR EVENT")
            duration = calendar.get("next_duration", "")
            if duration:
                secondary = f"{secondary} - {duration}"
            return f"NEXT {calendar.get('next_time', 'CAL')}", secondary

        if event is not None:
            secondary = getattr(event, "summary", "") or "CALENDAR EVENT"
            duration = getattr(event, "dur_str", "")
            if duration:
                secondary = f"{secondary} - {duration}"
            return f"NEXT {self._overview_event_time(event)}", secondary

        if weather["available"]:
            return weather["temperature"], (
                f"{weather['description']} - {weather['detail']}"
            )

        return "OVERVIEW", "WAITING FOR LIVE DATA"

    @staticmethod
    def _overview_calendar_detail(event) -> str:
        if getattr(event, "end_time_str", ""):
            return f"{getattr(event, 'time_str', '')}-{event.end_time_str}"
        if getattr(event, "time_str", "").upper() == "ALL DAY":
            return "ALL DAY"
        return "CALENDAR EVENT"

    @staticmethod
    def _overview_event_time(event) -> str:
        if event is None:
            return "--"
        time_label = str(getattr(event, "time_str", "") or "--").upper()
        if time_label == "ALL DAY":
            return "ALLDY"
        return time_label[:5]

    def _overview_next_calendar_event(self, events: list, now: _dt.datetime):
        for event in events:
            if self._overview_is_future_event(event, now):
                return event
        return None

    @staticmethod
    def _overview_is_future_event(event, now: _dt.datetime) -> bool:
        start_at = getattr(event, "start_at", None)
        if start_at is not None:
            if start_at.tzinfo is not None:
                now = _dt.datetime.now(start_at.tzinfo)
            return start_at > now

        event_date = getattr(event, "event_date", None)
        if event_date is None:
            return False
        return event_date > now.date()

    @staticmethod
    def _row_right(content: BoardContent, label: str) -> str:
        wanted = label.upper()
        for row in getattr(content, "rows", []) or []:
            if str(getattr(row, "left", "")).upper() == wanted:
                return str(getattr(row, "right", "") or "").upper()
        return ""

    @staticmethod
    def _highlighted_event_row(content: BoardContent):
        section_labels = {"TODAY", "TOMORROW", "THIS WEEK", "NO EVENTS"}
        first_event = None
        for row in getattr(content, "rows", []) or []:
            left = str(getattr(row, "left", "") or "").strip()
            if not left or left.upper() in section_labels:
                continue
            if getattr(row, "highlight", False):
                return row
            if first_event is None:
                first_event = row
        return first_event

    @staticmethod
    def _calendar_today_summary(content: BoardContent) -> str:
        for row in getattr(content, "rows", []) or []:
            if str(getattr(row, "left", "")).upper() == "TODAY":
                right = str(getattr(row, "right", "") or "").upper()
                return right.replace(" EVENTS", " TODAY").replace(" EVENT", " TODAY")
        return ""

    def _calendar_next_time(self, content: BoardContent, event_row) -> str:
        status = str(getattr(content, "status_text", "") or "").upper()
        if status.startswith("NEXT "):
            return status[5:10] if status != "NEXT ALL DAY" else "ALLDY"
        if event_row is None:
            return ""
        label = str(getattr(event_row, "left", "") or "")
        for token in label.split():
            if ":" in token:
                return token[:5]
            if token.upper() == "ALL":
                return "ALLDY"
        return "CAL"

    @staticmethod
    def _calendar_event_parts(label: str) -> tuple:
        text = str(label or "").strip()
        if not text:
            return "", ""
        prefix, sep, summary = text.partition("  ")
        if not sep:
            return text, "CALENDAR EVENT"
        return summary.strip() or prefix.strip(), prefix.strip()

    def _overview_location(self, weather: dict) -> str:
        city = str(weather.get("city", "")).strip()
        if city:
            return city
        return self._weather_location_label() or "PIBOARD"

    @staticmethod
    def _overview_sync_value(weather: dict, calendar: dict) -> str:
        live = sum(1 for item in (weather, calendar) if item.get("state") == "LIVE")
        stale = sum(1 for item in (weather, calendar) if item.get("state") == "STALE")
        if live == 2:
            return "WX/CAL LIVE"
        if live:
            return "PARTIAL"
        if stale:
            return "STALE"
        return "WAITING"

    def _overview_status(self, weather: dict, calendar: dict) -> tuple:
        value = self._overview_sync_value(weather, calendar)
        if value == "WX/CAL LIVE":
            return "LIVE", "green"
        if value == "STALE":
            return "STALE", "orange"
        if value == "WAITING":
            return "WAITING", "orange"
        return "PARTIAL", "orange"

    def _overview_status_color(self, weather: dict, calendar: dict) -> str:
        return self._overview_status(weather, calendar)[1]

    @staticmethod
    def _linked_source_data(provider):
        source = getattr(provider, "_source", None)
        getter = getattr(source, "get_data", None)
        if callable(getter):
            return getter()
        return None

    @staticmethod
    def _linked_content(provider):
        if provider is None:
            return None
        content = provider.get_content()
        if content.subtitle == "Loading...":
            return None
        return content

    def _freshness(self, fetched_at, provider, now: _dt.datetime) -> tuple:
        try:
            fetched_at = float(fetched_at)
        except (TypeError, ValueError):
            fetched_at = 0.0
        if fetched_at <= 0:
            return "WAIT", "orange"

        interval = self.default_refresh_interval
        if provider is not None:
            try:
                interval = float(provider.get_refresh_interval())
            except (TypeError, ValueError):
                interval = float(getattr(provider, "default_refresh_interval", interval))
        stale_after = max(600.0, interval * 3.0)
        return (
            ("STALE", "orange")
            if now.timestamp() - fetched_at > stale_after
            else ("LIVE", "green")
        )

    def _content_freshness(self, content: BoardContent, provider,
                           now: _dt.datetime) -> tuple:
        expires_at = getattr(content, "expires_at", None)
        if expires_at is not None and expires_at < now.timestamp():
            return "STALE", "orange"
        return self._freshness(self._content_fetched_at(content), provider, now)

    @staticmethod
    def _content_fetched_at(content: BoardContent) -> float:
        expires_at = getattr(content, "expires_at", None)
        if expires_at is not None:
            return float(expires_at) - 600.0
        return _time.time()

    @staticmethod
    def _source_config(provider_id: str) -> dict:
        try:
            from state import app_state
            return app_state.get_source_config(provider_id)
        except Exception:
            return {}

    @staticmethod
    def _round_to_quarter(dt: _dt.datetime) -> _dt.datetime:
        minute = ((dt.minute + 14) // 15) * 15
        dt = dt.replace(second=0, microsecond=0)
        if minute >= 60:
            return (dt.replace(minute=0) + _dt.timedelta(hours=1))
        return dt.replace(minute=minute)

    def _train_preset(self) -> BoardContent:
        live_content = self._linked_train_content()
        if live_content is not None:
            return live_content

        now = _dt.datetime.now()
        updated = now.strftime("%H:%M")
        return BoardContent(
            header_left="RAIL",
            header_right="",
            header_right_clock_format="%H:%M",
            title="Kings Lynn",
            title_color="amber",
            subtitle="Calling at:",
            page_label="PLATFORM 7",
            subtitle_color="dim",
            rows=[
                BoardRow("Cambridge",       "(12:30)", highlight=True),
                BoardRow("Cambridge North", "(12:39)"),
                BoardRow("Waterbeach",      "(12:44)"),
                BoardRow("Ely",             "(12:53)"),
                BoardRow(""),
                BoardRow("OPERATOR",  "GREAT NORTHERN",
                         left_color="dim", right_color="dim"),
                BoardRow("PLATFORM",  "7",
                         left_color="dim", right_color="dim"),
                BoardRow("FORMED OF", "8 COACHES",
                         left_color="dim", right_color="dim"),
                BoardRow("SERVICE",   "ON TIME",
                         left_color="dim", right_color="green"),
                BoardRow("UPDATED",   updated,
                         left_color="dim", right_color="dim"),
            ],
            footer="Great Northern",
            footer_color="dim",
            status_text="ON TIME",
            status_color="green",
            ticker="Great Northern service to Kings Lynn. Platform 7. "
                   f"Formed of 8 coaches. Updated {updated}.",
            carriage_hint="8",
            template="train",
            title_size="LARGE",
            provider_id="mock",
        )

    def _linked_train_content(self):
        if self._linked_train_provider is None:
            return None
        content = self._linked_train_provider.get_content()
        if content.subtitle == "Loading...":
            return None
        return copy.deepcopy(content)

    def _weather_preset(self) -> BoardContent:
        live_content = self._linked_weather_content()
        if live_content is not None:
            return live_content

        now = _dt.datetime.now()
        updated = now.strftime("%H:%M")
        city = self._weather_location_label()
        city_upper = city.upper()
        return BoardContent(
            header_left="WEATHER",
            header_right="",
            header_right_clock_format="%H:%M",
            title="14\u00b0C",
            title_color="amber",
            title_size="AUTO",
            subtitle="PARTLY CLOUDY",
            subtitle_color="dim",
            page_label=f"{city_upper} UPD {updated}",
            rows=[
                BoardRow("NOW",        "PARTLY CLOUDY",
                         right_color="white", highlight=True),
                BoardRow("FEELS",      "11\u00b0C"),
                BoardRow("WIND",       "SW 18KM/H"),
                BoardRow("HUMIDITY",   "72%"),
                BoardRow("VISIBILITY", "10KM"),
                BoardRow("UV INDEX",   "LOW"),
                BoardRow(""),
                BoardRow("TODAY",      "12\u00b0C/8\u00b0C"),
                BoardRow("FORECAST",   "2 DAYS",
                         left_color="dim", right_color="dim"),
                BoardRow("WED",        "15\u00b0C / 9\u00b0C",
                         left_color="dim", right_color="dim"),
                BoardRow("THU",        "11\u00b0C / 7\u00b0C",
                         left_color="dim", right_color="dim"),
            ],
            footer="Weather demo (mock)",
            footer_color="dim",
            status_text="DEMO",
            status_color="orange",
            ticker=f"{city}: Partly cloudy. Now 14\u00b0C. Feels like 11\u00b0C. "
                   f"Wind SW 18KM/H. Today 12\u00b0C/8\u00b0C. Updated {updated}.",
            template="info",
            provider_id="mock",
        )

    def _linked_weather_content(self):
        if self._linked_weather_provider is None:
            return None
        content = self._linked_weather_provider.get_content()
        if content.subtitle == "Loading...":
            return None
        return copy.deepcopy(content)

    def _weather_location_label(self) -> str:
        try:
            from state import app_state
            cfg = app_state.get_source_config("weather")
        except Exception:
            cfg = {}
        city = str(cfg.get("city", "")).strip()
        if cfg.get("location_mode", "auto") == "auto":
            return city or "当前位置"
        return city or "Beijing"

    def _calendar_preset(self) -> BoardContent:
        live_content = self._linked_calendar_content()
        if live_content is not None:
            return live_content

        today = _dt.date.today()
        week_1 = today + _dt.timedelta(days=2)
        week_2 = today + _dt.timedelta(days=3)
        return BoardContent(
            header_left=today.strftime("%a").upper(),
            header_right=today.strftime("%d %b").upper(),
            title="",
            title_clock_format="%H:%M",
            title_color="amber",
            title_size="XLARGE",
            subtitle="NEXT 09:00 - 3 EVENTS TODAY",
            subtitle_color="dim",
            rows=[
                BoardRow("TODAY",                 "3 EVENTS",
                         left_color="dim", right_color="dim"),
                BoardRow("09:00  Team standup",   "30min", highlight=True),
                BoardRow("14:00  Dentist",         "1hr"),
                BoardRow("19:30  Dinner - Marks",  "2hr"),
                BoardRow(""),
                BoardRow("TOMORROW",               "2 EVENTS",
                         left_color="dim", right_color="dim"),
                BoardRow("10:00  Code review",     "1hr",
                         left_color="dim", right_color="dim"),
                BoardRow("16:00  Weekly sync",     "45min",
                         left_color="dim", right_color="dim"),
                BoardRow(""),
                BoardRow("THIS WEEK",              "2 EVENTS",
                         left_color="dim", right_color="dim"),
                BoardRow(f"{week_1:%a}".upper() + " 11:30  Ticket release",
                         "15min", left_color="dim", right_color="dim"),
                BoardRow(f"{week_2:%a}".upper() + " 18:00  Project wrap",
                         "1hr", left_color="dim", right_color="dim"),
            ],
            footer="Google Calendar (mock)",
            footer_color="dim",
            status_text="NEXT 09:00",
            status_color="green",
            ticker="TODAY 3 EVENTS - TOMORROW 2 EVENTS - THIS WEEK 2 EVENTS",
            template="info",
            provider_id="mock",
        )

    def _linked_calendar_content(self):
        if self._linked_calendar_provider is None:
            return None
        content = self._linked_calendar_provider.get_content()
        if content.subtitle == "Loading...":
            return None
        return copy.deepcopy(content)


# 允许单独运行快速验证
if __name__ == "__main__":
    p = MockProvider(config={"preset": "cycle"})
    for i in range(4):
        c = p.fetch()
        print(f"Preset {i}: title={c.title!r}, rows={len(c.rows)}, "
              f"status={c.status_text!r}")
