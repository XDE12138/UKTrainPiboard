"""
TrainSource：列车数据获取与归一化。

mock 路径提供稳定演示数据；huxley2 路径提供 live departures 归一化。
transportapi 暂由 TrainSourceBridge 回退到旧 TrainProvider。

职责边界：
- 从外部（mock / 未来 API）获取原始数据，归一化为 TrainBoardData
- 不构造 BoardContent，不做任何渲染相关判断
- 写入 self._cached_data，满足 BaseSource 约定
"""
import logging
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import List, Tuple
from sources.base import BaseSource

HUXLEY2_BASE = "https://huxley2.azurewebsites.net"
log = logging.getLogger(__name__)


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        if data.strip():
            self.parts.append(data.strip())

    def text(self):
        return " ".join(self.parts)


@dataclass
class TrainDeparture:
    """单条列车出发记录（归一化 schema）。"""
    destination: str                        # 终点站名，如 "Edinburgh"
    scheduled_dep: str                      # 计划时刻，"HH:MM"
    estimated_dep: str                      # 预计时刻，"HH:MM" / "On time" / "Delayed"
    platform: str                           # 站台号，"" 表示未知
    operator: str                           # 运营商，如 "LNER"
    calling_at: List[Tuple[str, str]]       # 途经站：(站名, 时刻)，如 [("Newcastle", "12:35"), ...]
    is_cancelled: bool = False


@dataclass
class TrainBoardData:
    """出发板归一化数据（TrainSource 的输出格式）。"""
    station_name: str
    station_crs: str
    departures: List[TrainDeparture]
    messages: List[str]                     # 站台公告，本轮 mock 返回 []
    fetched_at: float                       # Unix timestamp
    mode: str = "calling_at"                # calling_at | departures
    error: str = ""                         # live source failure summary, empty when OK


class TrainSource(BaseSource):
    """
    列车数据 Source。

    实现 mock 与 huxley2 路径；transportapi 暂由旧 Provider 处理。
    构造时接收 config dict，与 TrainProvider 保持相同配置键名。
    """

    def __init__(self, config: dict = None, force_mock: bool = False):
        super().__init__("train", force_mock=force_mock)
        self.config = config or {}

    def fetch(self) -> TrainBoardData:
        """
        获取并归一化列车数据。

        mock 返回稳定演示数据；huxley2 返回 live departure board 数据。
        transportapi 仍由 TrainSourceBridge 显式 fallback 到旧 TrainProvider。
        """
        data_source = self.config.get("data_source", "mock")
        if data_source == "mock":
            data = self._mock_data()
            self._cached_data = data
            return data
        if data_source == "huxley2":
            data = self._huxley2_data()
            self._cached_data = data
            return data
        raise NotImplementedError(
            f"TrainSource.fetch() only implements mock and huxley2 paths. "
            f"data_source='{data_source}' is not yet supported here. "
            f"transportapi is handled by TrainSourceBridge via fallback "
            f"to the legacy TrainProvider."
        )

    # ------------------------------------------------------------------
    # Mock 路径
    # ------------------------------------------------------------------

    def _mock_data(self) -> TrainBoardData:
        """
        返回与旧 TrainProvider._mock_content() 语义等价的归一化数据。
        固定为 KGX → Edinburgh，LNER Azuma，4 个途经站（含时刻）。
        """
        crs = self.config.get("station_crs", "KGX").upper()
        return TrainBoardData(
            station_name="King's Cross",
            station_crs=crs,
            departures=[
                TrainDeparture(
                    destination="Edinburgh",
                    scheduled_dep="14:35",
                    estimated_dep="On time",
                    platform="9",
                    operator="LNER Azuma",
                    calling_at=[
                        ("Newcastle",          "12:35"),
                        ("Morpeth",            "12:59"),
                        ("Alnmouth (Alnwick)", "13:07"),
                        ("& Edinburgh",        "14:15"),
                    ],
                    is_cancelled=False,
                )
            ],
            messages=[],
            fetched_at=time.time(),
            mode="calling_at",
        )

    # ------------------------------------------------------------------
    # Huxley2 路径
    # ------------------------------------------------------------------

    def _huxley2_data(self) -> TrainBoardData:
        """Fetch live departures from Huxley2 and normalize them."""
        crs = self.config.get("station_crs", "KGX").upper()
        try:
            import requests
        except ImportError as exc:
            return self._huxley2_unavailable(crs=crs,
                                             reason="NO REQUESTS",
                                             exc=exc)

        dest = self.config.get("destination_crs", "").upper()
        if dest:
            url = f"{HUXLEY2_BASE}/departures/{crs}/to/{dest}/10"
        else:
            url = f"{HUXLEY2_BASE}/departures/{crs}/10"

        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            payload = resp.json()
        except (requests.RequestException, ValueError) as exc:
            reason = "NETWORK"
            if isinstance(exc, requests.HTTPError) and exc.response is not None:
                reason = f"HTTP {exc.response.status_code}"
            elif isinstance(exc, requests.Timeout):
                reason = "TIMEOUT"
            elif isinstance(exc, ValueError):
                reason = "BAD DATA"
            log.warning("Huxley2 unavailable [%s]: %s", crs, reason)
            return self._huxley2_unavailable(crs=crs, reason=reason, exc=exc)

        departures = []
        for svc in payload.get("trainServices") or []:
            departures.append(self._normalize_huxley_service(svc))

        return TrainBoardData(
            station_name=payload.get("locationName") or crs,
            station_crs=payload.get("crs") or crs,
            departures=departures,
            messages=self._normalize_messages(payload),
            fetched_at=time.time(),
            mode="departures",
        )

    @staticmethod
    def _huxley2_unavailable(
            crs: str, reason: str, exc: Exception) -> TrainBoardData:
        _ = exc
        station = crs or "RAIL"
        return TrainBoardData(
            station_name=station,
            station_crs=station,
            departures=[],
            messages=[],
            fetched_at=time.time(),
            mode="departures",
            error=reason,
        )

    @staticmethod
    def _normalize_huxley_service(svc: dict) -> TrainDeparture:
        destination = "Unknown"
        destinations = svc.get("destination") or []
        if destinations:
            destination = destinations[0].get("locationName") or destination

        return TrainDeparture(
            destination=destination,
            scheduled_dep=svc.get("std") or "",
            estimated_dep=svc.get("etd") or "",
            platform=svc.get("platform") or "",
            operator=svc.get("operator") or "National Rail",
            calling_at=[],
            is_cancelled=bool(svc.get("isCancelled")),
        )

    @staticmethod
    def _normalize_messages(payload: dict) -> List[str]:
        messages = []
        for msg in payload.get("nrccMessages") or []:
            value = msg.get("value") if isinstance(msg, dict) else str(msg)
            if value:
                parser = _TextExtractor()
                parser.feed(str(value))
                text = parser.text() or str(value)
                messages.append(text)
        return messages
