"""
CalendarSource：日程数据获取与归一化。

职责边界：
- 从外部（mock / iCal）获取原始数据，归一化为 CalendarSchedule
- 不构造 BoardContent，不做任何渲染相关判断
- 写入 self._cached_data，满足 BaseSource 约定

routing 条件：
  not config.get("ical_url", "") => mock 路径（_mock_data）
  有 ical_url                    => live 路径（_live_data），异常 fail-loud
"""
import time
import datetime
import logging
import os
import requests
from dataclasses import dataclass
from typing import List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sources.base import BaseSource

log = logging.getLogger(__name__)


@dataclass
class CalendarEvent:
    """单个日程事件的归一化数据。"""
    event_date: datetime.date                 # 事件日期
    start_at: Optional[datetime.datetime]     # 事件开始时间（全天事件为 None）
    time_str: str                             # 显示用时间字符串："HH:MM" / "All day"
    summary: str                              # 事件标题
    dur_str: str                              # 时长字符串："30min" / "1hr" / ""
    end_at: Optional[datetime.datetime] = None
    end_time_str: str = ""


@dataclass
class CalendarSchedule:
    """CalendarSource 的归一化输出格式。"""
    today: datetime.date                      # 取数据时的"今天"
    events: List[CalendarEvent]               # 当前 lookahead 窗口内的所有事件（未排序）
    fetched_at: float                         # Unix timestamp
    source_label: str = "Google Calendar (mock)"  # footer 用标签：mock 或 live 路径各自设置


class CalendarSource(BaseSource):
    """
    日程数据 Source。

    构造时接收 config dict，与 CalendarProvider 保持相同配置键名。
    """

    def __init__(self, config: dict = None, force_mock: bool = False):
        super().__init__("calendar", force_mock=force_mock)
        self.config = config or {}

    def fetch(self) -> CalendarSchedule:
        """
        获取并归一化日程数据。

        无 ical_url → mock 路径。
        有 ical_url → live iCal 路径，异常 fail-loud（不 fallback 到 mock）。
        """
        ical_url = self.config.get("ical_url", "")
        if not ical_url:
            data = self._mock_data()
            self._cached_data = data
            return data
        data = self._live_data(ical_url)
        self._cached_data = data
        return data

    # ------------------------------------------------------------------
    # Live 路径
    # ------------------------------------------------------------------

    def _live_data(self, url: str) -> CalendarSchedule:
        """
        拉取并归一化 iCal 数据。

        解析语义与旧 CalendarProvider._fetch_ical() 保持一致。
        异常（网络、解析）fail-loud，由 DataFetcher 保留旧缓存。
        """
        from icalendar import Calendar

        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        cal = Calendar.from_ical(resp.content)

        lookahead = int(self.config.get("lookahead_days", 3))
        local_tz = self._local_timezone()
        today = datetime.datetime.now(local_tz).date()
        end_date = today + datetime.timedelta(days=lookahead)

        events: List[CalendarEvent] = []
        for component in cal.walk():
            if component.name != "VEVENT":
                continue
            dtstart = component.get("DTSTART")
            if dtstart is None:
                continue
            dt = dtstart.dt
            if isinstance(dt, datetime.datetime):
                start_at = self._to_local_datetime(dt, local_tz)
                event_date = start_at.date()
                time_str = start_at.strftime("%H:%M")
            else:
                event_date = dt
                time_str = "All day"
                start_at = None

            if not (today <= event_date <= end_date):
                continue

            summary = str(component.get("SUMMARY", ""))
            dtend = component.get("DTEND")
            dur_str = ""
            end_at: Optional[datetime.datetime] = None
            end_time_str = ""
            if dtend:
                end_dt = dtend.dt
                if isinstance(end_dt, datetime.datetime) and isinstance(dt, datetime.datetime):
                    end_at = self._to_local_datetime(end_dt, local_tz)
                    delta = end_at - start_at
                    mins = int(delta.total_seconds() / 60)
                    dur_str = self._format_duration(mins)
                    end_time_str = self._format_end_time(event_date, end_at)

            events.append(CalendarEvent(
                event_date=event_date,
                start_at=start_at,
                time_str=time_str,
                summary=summary,
                dur_str=dur_str,
                end_at=end_at,
                end_time_str=end_time_str,
            ))

        return CalendarSchedule(
            today=today,
            events=events,
            fetched_at=time.time(),
            source_label="Calendar",
        )

    @staticmethod
    def _local_timezone() -> datetime.tzinfo:
        """Return the device's current local timezone."""
        tz_name = CalendarSource._local_timezone_name()
        if tz_name:
            try:
                return ZoneInfo(tz_name)
            except ZoneInfoNotFoundError:
                pass
        return datetime.datetime.now().astimezone().tzinfo

    @staticmethod
    def _local_timezone_name() -> str:
        env_tz = os.environ.get("TZ", "").strip()
        if env_tz and not env_tz.startswith(":"):
            return env_tz

        try:
            with open("/etc/timezone", "r", encoding="utf-8") as f:
                tz_name = f.read().strip()
                if tz_name:
                    return tz_name
        except OSError:
            pass

        try:
            localtime = os.path.realpath("/etc/localtime")
        except OSError:
            return ""

        marker = "/zoneinfo/"
        if marker in localtime:
            return localtime.split(marker, 1)[1]
        return ""

    @staticmethod
    def _to_local_datetime(dt: datetime.datetime,
                           local_tz: datetime.tzinfo) -> datetime.datetime:
        """Normalize iCal datetimes to the device timezone before display."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=local_tz)
        return dt.astimezone(local_tz)

    @staticmethod
    def _format_duration(minutes: int) -> str:
        if minutes <= 0:
            return ""
        hours, mins = divmod(minutes, 60)
        if hours and mins:
            return f"{hours}H{mins:02d}"
        if hours:
            return f"{hours}H"
        return f"{mins}M"

    @staticmethod
    def _format_end_time(event_date: datetime.date,
                         end_at: datetime.datetime) -> str:
        if end_at.date() == event_date:
            return end_at.strftime("%H:%M")
        return end_at.strftime("%d %H:%M")

    # ------------------------------------------------------------------
    # Mock 路径
    # ------------------------------------------------------------------

    def _mock_data(self) -> CalendarSchedule:
        """
        返回与旧 CalendarProvider._mock_content() 语义等价的归一化数据。
        事件顺序与旧 mock 保持一致，排序由 CalendarToUKBinding 负责。
        """
        today = datetime.date.today()
        tomorrow = today + datetime.timedelta(days=1)

        events = [
            CalendarEvent(
                event_date=today,
                start_at=datetime.datetime.combine(today, datetime.time(9, 0)),
                time_str="09:00",
                summary="Team standup",
                dur_str="30M",
                end_at=datetime.datetime.combine(today, datetime.time(9, 30)),
                end_time_str="09:30",
            ),
            CalendarEvent(
                event_date=today,
                start_at=datetime.datetime.combine(today, datetime.time(14, 0)),
                time_str="14:00",
                summary="Dentist",
                dur_str="1H",
                end_at=datetime.datetime.combine(today, datetime.time(15, 0)),
                end_time_str="15:00",
            ),
            CalendarEvent(
                event_date=today,
                start_at=datetime.datetime.combine(today, datetime.time(19, 30)),
                time_str="19:30",
                summary="Dinner - Marks",
                dur_str="2H",
                end_at=datetime.datetime.combine(today, datetime.time(21, 30)),
                end_time_str="21:30",
            ),
            CalendarEvent(
                event_date=tomorrow,
                start_at=datetime.datetime.combine(tomorrow, datetime.time(10, 0)),
                time_str="10:00",
                summary="Code review",
                dur_str="1H",
                end_at=datetime.datetime.combine(tomorrow, datetime.time(11, 0)),
                end_time_str="11:00",
            ),
            CalendarEvent(
                event_date=tomorrow,
                start_at=datetime.datetime.combine(tomorrow, datetime.time(16, 0)),
                time_str="16:00",
                summary="Weekly sync",
                dur_str="45M",
                end_at=datetime.datetime.combine(tomorrow, datetime.time(16, 45)),
                end_time_str="16:45",
            ),
        ]

        return CalendarSchedule(
            today=today,
            events=events,
            fetched_at=time.time(),
            source_label="Google Calendar (mock)",
        )
