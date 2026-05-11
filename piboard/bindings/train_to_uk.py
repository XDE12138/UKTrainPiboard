"""
TrainToUKBinding：将 TrainBoardData 映射为 BoardContent。

职责边界：
- 输入：TrainBoardData（TrainSource 的归一化输出）
- 输出：BoardContent（与现有 UKStationApp / layouts / board_renderer 完全兼容）
- 不做网络请求，不读 config，不感知外部 API 格式
- 渲染判断（颜色、布局）在这里决定，不在 Source 里

mock 输出保持单趟车 calling-at 板；huxley2 live 输出为
"下一班主视觉 + 后续出发列表" 的混合版 departure board。
"""
from datetime import datetime
from zoneinfo import ZoneInfo
import time
from bindings.base import BaseBinding
from board.content import BoardContent, BoardRow
from sources.train import TrainBoardData


class TrainToUKBinding(BaseBinding):
    """
    将 TrainBoardData 转换为英国车站信息屏风格的 BoardContent。
    """

    source_id = "train"
    app_slot = "uk_station"
    _MIN_CALLING_ROWS = 6
    _CARRIAGE_HINT = "8"

    def transform(self, raw: TrainBoardData) -> BoardContent:
        if raw.mode == "departures":
            return self._transform_departures(raw)
        return self._transform_calling_at(raw)

    def _transform_calling_at(self, raw: TrainBoardData) -> BoardContent:
        """
        Detail Board 结构：
          title        = destination
          subtitle     = "Calling at:" + page label
          rows         = calling_at；少于阈值时追加 operator/platform/status/updated
          status       = service health
          ticker       = service meta 的低优先级补充
        """
        if not raw.departures:
            return BoardContent(
                title="No services",
                provider_id="train",
                status_text="--",
                status_color="dim",
            )

        dep = raw.departures[0]
        platform = dep.platform.strip()
        status_text, status_color = "DEMO", "orange"
        updated = time.strftime("%H:%M", time.localtime(raw.fetched_at))

        rows = []
        for i, (station_name, station_time) in enumerate(dep.calling_at):
            rows.append(BoardRow(
                left=station_name,
                right=station_time,
                highlight=(i == 0),
            ))

        if len(rows) < self._MIN_CALLING_ROWS:
            rows.extend(self._service_meta_rows(
                raw=raw,
                dep=dep,
                platform=platform,
                status_text=status_text,
                status_color=status_color,
                updated=updated,
            ))

        return BoardContent(
            header_left="RAIL",
            header_right="",
            header_right_clock_format="%H:%M",
            title=dep.destination,
            subtitle="Calling at:",
            page_label=f"PLATFORM {platform}" if platform else raw.station_crs,
            rows=rows,
            footer="Rail demo data (mock)",
            status_text=status_text,
            status_color=status_color,
            ticker=(
                "Demo rail data only. Configure Train data_source=huxley2 "
                "for live departures. "
                + self._ticker(raw, dep, platform, updated)
            ),
            carriage_hint=self._CARRIAGE_HINT,
            template="train",
            title_size="LARGE",
            provider_id="train",
            expires_at=raw.fetched_at + 60,
        )

    def _transform_departures(self, raw: TrainBoardData) -> BoardContent:
        """Render a live station departures board for Huxley2 data."""
        updated_uk = self._uk_time_label(raw.fetched_at)
        source_label = f"{raw.station_crs} LIVE DEPARTURES"

        if raw.error:
            return self._transform_departures_unavailable(
                raw=raw,
                updated_uk=updated_uk,
                source_label=source_label,
            )

        if not raw.departures:
            return BoardContent(
                header_left="RAIL",
                header_right="",
                header_right_clock_format="%H:%M CN",
                title="NO SERVICES",
                subtitle=raw.station_name.upper(),
                page_label="CHECK LATER",
                rows=[
                    BoardRow("STATION", raw.station_crs,
                             left_color="dim", right_color="dim"),
                    BoardRow("SOURCE", "HUXLEY2",
                             left_color="dim", right_color="dim"),
                    BoardRow("UPDATED", f"{updated_uk} UK",
                             left_color="dim", right_color="dim"),
                ],
                footer=source_label,
                status_text="CHECK LATER",
                status_color="orange",
                ticker=self._live_ticker(raw.station_crs, updated_uk),
                template="info",
                title_size="LARGE",
                provider_id="train",
                expires_at=raw.fetched_at + 60,
            )

        dep = raw.departures[0]
        platform = dep.platform.strip()
        status_text, status_color = self._service_status(dep)
        scheduled = dep.scheduled_dep or self._display_time(dep)

        rows = []
        for i, later in enumerate(raw.departures[1:7]):
            rows.append(self._departure_row(later, highlight=(i == 0)))

        if not rows:
            rows.append(BoardRow("NO FURTHER SERVICES", "", left_color="dim"))

        ticker = self._live_ticker(raw.station_crs, updated_uk)
        if raw.messages:
            ticker = f"{ticker} {' '.join(raw.messages)}"

        return BoardContent(
            header_left="RAIL",
            header_right="",
            header_right_clock_format="%H:%M CN",
            title=self._title_destination(dep.destination),
            subtitle=f"NEXT {scheduled} UK" if scheduled else "NEXT -- UK",
            subtitle_color="amber",
            page_label=f"PLATFORM {platform}" if platform else raw.station_crs,
            rows=rows,
            footer=source_label,
            status_text=status_text,
            status_color=status_color,
            ticker=ticker,
            template="train",
            title_size="AUTO",
            provider_id="train",
            expires_at=raw.fetched_at + 60,
        )

    def _transform_departures_unavailable(
            self, raw: TrainBoardData, updated_uk: str,
            source_label: str) -> BoardContent:
        reason = (raw.error or "UNAVAILABLE").upper()
        return BoardContent(
            header_left="RAIL",
            header_right="",
            header_right_clock_format="%H:%M CN",
            title="LIVE DATA OFF",
            subtitle=f"{raw.station_crs} DEPARTURES",
            subtitle_color="amber",
            page_label="RETRYING",
            rows=[
                BoardRow("STATION", raw.station_crs,
                         highlight=True),
                BoardRow("SOURCE", "HUXLEY2",
                         left_color="dim", right_color="amber"),
                BoardRow("STATUS", reason,
                         left_color="dim", right_color="orange"),
                BoardRow("LAST TRY", f"{updated_uk} UK",
                         left_color="dim", right_color="dim"),
                BoardRow("DISPLAY", "STILL RUNNING",
                         left_color="dim", right_color="green"),
            ],
            footer=source_label,
            status_text="RETRYING",
            status_color="orange",
            ticker=(
                f"{raw.station_crs} live departures temporarily unavailable. "
                f"Data via Huxley2. Retrying every minute."
            ),
            template="info",
            title_size="LARGE",
            provider_id="train",
            expires_at=raw.fetched_at + 60,
        )

    def _service_status(self, dep):
        if dep.is_cancelled:
            return "CANCELLED", "red"

        status = (dep.estimated_dep or "").strip()
        status_upper = status.upper()
        if status_upper in ("", "ON TIME"):
            return "ON TIME", "green"
        if "CANCEL" in status_upper or "DELAY" in status_upper:
            return status_upper, "red"
        return f"EXP {status_upper}", "orange"

    def _departure_row(self, dep, highlight=False):
        if dep.is_cancelled:
            return BoardRow(
                dep.destination,
                "CANCELLED",
                right_color="red",
                highlight=highlight,
            )

        status = (dep.estimated_dep or "").strip()
        status_upper = status.upper()
        right_color = "amber"

        if status_upper in ("", "ON TIME"):
            label = dep.scheduled_dep
        elif "DELAY" in status_upper:
            label = status_upper
            right_color = "red"
        elif self._looks_like_time(status):
            label = status
            right_color = "orange"
        else:
            label = status_upper
            right_color = "orange"

        if self._looks_like_time(label):
            label = f"{label} UK"

        return BoardRow(
            dep.destination,
            label,
            right_color=right_color,
            highlight=highlight,
        )

    @staticmethod
    def _display_time(dep):
        status = (dep.estimated_dep or "").strip()
        if TrainToUKBinding._looks_like_time(status):
            return status
        return dep.scheduled_dep

    @staticmethod
    def _looks_like_time(value: str) -> bool:
        if not value or len(value) != 5:
            return False
        return value[0:2].isdigit() and value[2] == ":" and value[3:5].isdigit()

    @staticmethod
    def _uk_time_label(timestamp: float) -> str:
        return datetime.fromtimestamp(timestamp, ZoneInfo("Europe/London")).strftime("%H:%M")

    @staticmethod
    def _live_ticker(station_crs: str, updated_uk: str) -> str:
        return (
            f"{station_crs} live departures. UK rail times. "
            f"Data via Huxley2. Updated {updated_uk} UK."
        )

    @staticmethod
    def _title_destination(destination: str) -> str:
        text = (destination or "Unknown").strip()
        replacements = {
            "Birmingham International": "Birmingham Intl",
            "Manchester Piccadilly": "Manchester Picc",
            "Liverpool Lime Street": "Liverpool Lime",
            "Worcester Foregate Street": "Worcester F St",
        }
        text = replacements.get(text, text)
        if len(text) <= 16:
            return text
        return text[:16].rstrip()

    def _service_meta_rows(self, raw, dep, platform, status_text, status_color, updated):
        rows = [BoardRow("")]
        rows.append(BoardRow(
            "OPERATOR",
            dep.operator.upper(),
            left_color="dim",
            right_color="dim",
        ))
        rows.append(BoardRow(
            "PLATFORM",
            platform or raw.station_crs,
            left_color="dim",
            right_color="dim",
        ))
        rows.append(BoardRow(
            "FORMED OF",
            f"{self._CARRIAGE_HINT} COACHES",
            left_color="dim",
            right_color="dim",
        ))
        rows.append(BoardRow(
            "SERVICE",
            status_text,
            left_color="dim",
            right_color=status_color,
        ))
        rows.append(BoardRow(
            "UPDATED",
            updated,
            left_color="dim",
            right_color="dim",
        ))
        return rows

    def _ticker(self, raw, dep, platform, updated):
        if raw.messages:
            return " ".join(raw.messages)

        platform_text = f" Platform {platform}." if platform else ""
        return (
            f"{dep.operator} service to {dep.destination}."
            f"{platform_text} Formed of {self._CARRIAGE_HINT} coaches. "
            f"Updated {updated}."
        )
