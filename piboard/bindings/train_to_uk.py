"""
TrainToUKBinding：将 TrainBoardData 映射为 BoardContent。

职责边界：
- 输入：TrainBoardData（TrainSource 的归一化输出）
- 输出：BoardContent（与现有 UKStationApp / layouts / board_renderer 完全兼容）
- 不做网络请求，不读 config，不感知外部 API 格式
- 渲染判断（颜色、布局）在这里决定，不在 Source 里

输出保持单趟车 calling-at 板的铁路语法；当 calling-at 较短时，
用 service meta 补足 Detail Board 的信息密度。
"""
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
        status_text, status_color = self._service_status(dep)
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
            footer=dep.operator,
            status_text=status_text,
            status_color=status_color,
            ticker=self._ticker(raw, dep, platform, updated),
            carriage_hint=self._CARRIAGE_HINT,
            template="train",
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
