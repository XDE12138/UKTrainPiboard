"""
CalendarToUKBinding：将 CalendarSchedule 映射为 UK Station BoardContent。

职责边界：
- 纯 transform：CalendarSchedule → BoardContent
- 不感知 ical_url / mock / live 概念，只处理已归一化的数据
- 负责计算 today_count / next_event_time（领域派生值，不由 Source 预计算）
- 负责按 TODAY / TOMORROW / THIS WEEK 分组渲染、颜色标注、状态文本

排序规则：
  先按 event_date，再按 start_at（all-day 事件 start_at=None，排在当天有时间事件之前）。
  sort key: (event_date, datetime.min if start_at is None else start_at.time())
"""
import datetime
from bindings.base import BaseBinding
from sources.calendar import CalendarSchedule
from board.content import BoardContent, BoardRow


class CalendarToUKBinding(BaseBinding):

    source_id = "calendar"
    app_slot = "uk_station"

    def transform(self, raw: CalendarSchedule) -> BoardContent:
        today = raw.today

        # 排序：all-day (start_at=None) 排在当天有时间事件之前
        sorted_events = sorted(
            raw.events,
            key=lambda e: (
                e.event_date,
                datetime.datetime.min.time() if e.start_at is None else e.start_at.time(),
            ),
        )

        # 统计今天事件数、下一个未来事件。
        # all-day 的今天事件是上下文，不作为 "NEXT"；未来日期的 all-day
        # 可以作为下一项显示为 NEXT ALL DAY。
        today_events = [e for e in sorted_events if e.event_date == today]
        today_count = len(today_events)
        next_event = self._next_future_event(sorted_events, raw.fetched_at)

        rows = self._build_rows(sorted_events, today, next_event, raw.fetched_at)
        status_text = self._status_text(next_event)

        return BoardContent(
            header_left="CALENDAR",
            header_right=today.strftime("%d %b").upper(),
            title="",
            title_clock_format="%H:%M",
            title_size="XLARGE",
            subtitle=self._clock_subtitle(today_count, next_event),
            rows=rows,
            footer=raw.source_label,
            status_text=status_text,
            status_color="green" if next_event else "dim",
            ticker=self._ticker(sorted_events, today),
            template="info",
            provider_id="calendar",
            expires_at=None,
        )

    # ------------------------------------------------------------------
    # 内部渲染
    # ------------------------------------------------------------------

    def _next_future_event(self, events: list, fetched_at: float):
        for event in events:
            if self._is_future_event(event, fetched_at):
                return event
        return None

    def _is_future_event(self, event, fetched_at: float) -> bool:
        current_dt = self._current_dt_for_event(event, fetched_at)

        if event.start_at is None:
            return event.event_date > current_dt.date()

        return event.start_at > current_dt

    @staticmethod
    def _current_dt_for_event(event, fetched_at: float) -> datetime.datetime:
        if event.start_at is not None and event.start_at.tzinfo is not None:
            return datetime.datetime.fromtimestamp(fetched_at, tz=event.start_at.tzinfo)
        return datetime.datetime.fromtimestamp(fetched_at)

    def _clock_subtitle(self, today_count: int, next_event) -> str:
        today_text = self._today_subtitle(today_count)
        if next_event:
            return f"{self._status_text(next_event)} - {today_text}"
        return today_text

    def _today_subtitle(self, today_count: int) -> str:
        if today_count:
            return f"{today_count} {self._plural(today_count, 'EVENT')} TODAY"
        return "NO EVENTS TODAY"

    def _status_text(self, next_event) -> str:
        if not next_event:
            return "NO EVENTS"
        if next_event.time_str.upper() == "ALL DAY":
            return "NEXT ALL DAY"
        return f"NEXT {next_event.time_str}"

    def _build_rows(self, events: list, today: datetime.date, next_event, fetched_at: float) -> list:
        tomorrow = today + datetime.timedelta(days=1)
        today_events = [e for e in events if e.event_date == today]
        tomorrow_events = [e for e in events if e.event_date == tomorrow]
        week_events = [e for e in events if e.event_date > tomorrow]

        rows = []
        rows.extend(self._section_rows(
            "TODAY", today_events, today, next_event, "amber", fetched_at,
        ))
        rows.append(BoardRow(""))
        rows.extend(self._section_rows(
            "TOMORROW", tomorrow_events, today, next_event, "dim", fetched_at,
        ))
        rows.append(BoardRow(""))
        rows.extend(self._section_rows(
            "THIS WEEK", week_events, today, next_event, "dim", fetched_at,
        ))
        return rows

    def _section_rows(self, label, events, today, next_event, event_color, fetched_at: float):
        rows = [
            BoardRow(
                label,
                f"{len(events)} {self._plural(len(events), 'EVENT')}",
                left_color="dim",
                right_color="dim",
            )
        ]

        if not events:
            rows.append(BoardRow("NO EVENTS", "", left_color="dim", right_color="dim"))
            return rows

        for event in events:
            color = self._event_row_color(event, event_color, fetched_at)
            rows.append(BoardRow(
                self._event_label(event, today),
                self._event_duration_label(event),
                left_color=color,
                right_color=color,
                highlight=(event is next_event),
            ))
        return rows

    def _event_row_color(self, event, event_color: str, fetched_at: float) -> str:
        if event_color != "amber":
            return event_color
        if event.start_at is None:
            return event_color
        return event_color if self._is_future_event(event, fetched_at) else "dim"

    def _event_label(self, event, today: datetime.date) -> str:
        tomorrow = today + datetime.timedelta(days=1)
        time_label = self._event_time_label(event)
        if event.event_date in (today, tomorrow):
            return f"{time_label}  {event.summary}"
        day = event.event_date.strftime("%a").upper()
        return f"{day} {time_label}  {event.summary}"

    @staticmethod
    def _event_time_label(event) -> str:
        if event.time_str.upper() == "ALL DAY":
            return event.time_str
        if getattr(event, "end_time_str", ""):
            return f"{event.time_str}-{event.end_time_str}"
        return event.time_str

    @staticmethod
    def _event_duration_label(event) -> str:
        return getattr(event, "dur_str", "") or ""

    def _ticker(self, events, today: datetime.date) -> str:
        tomorrow = today + datetime.timedelta(days=1)
        today_count = sum(1 for e in events if e.event_date == today)
        tomorrow_count = sum(1 for e in events if e.event_date == tomorrow)
        week_count = sum(1 for e in events if e.event_date > tomorrow)
        return (
            f"TODAY {today_count} {self._plural(today_count, 'EVENT')} - "
            f"TOMORROW {tomorrow_count} {self._plural(tomorrow_count, 'EVENT')} - "
            f"THIS WEEK {week_count} {self._plural(week_count, 'EVENT')}"
        )

    @staticmethod
    def _plural(count: int, singular: str) -> str:
        return singular if count == 1 else f"{singular}S"
