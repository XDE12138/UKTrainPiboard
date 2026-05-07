"""
TrainSource：列车数据获取与归一化。

本轮（Task 3）只实现 mock 路径作为第一条真实新链路。
huxley2 / transportapi 的归一化留到后续 Task，当前由 TrainSourceBridge 回退到旧 TrainProvider。

职责边界：
- 从外部（mock / 未来 API）获取原始数据，归一化为 TrainBoardData
- 不构造 BoardContent，不做任何渲染相关判断
- 写入 self._cached_data，满足 BaseSource 约定
"""
import time
from dataclasses import dataclass, field
from typing import List, Tuple
from sources.base import BaseSource


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
    departures: List[TrainDeparture]        # 本轮 mock 只返回 1 条
    messages: List[str]                     # 站台公告，本轮 mock 返回 []
    fetched_at: float                       # Unix timestamp


class TrainSource(BaseSource):
    """
    列车数据 Source。

    本轮只实现 mock 路径；huxley2 / transportapi 归一化留到后续 Task。
    构造时接收 config dict，与 TrainProvider 保持相同配置键名。
    """

    def __init__(self, config: dict = None, force_mock: bool = False):
        super().__init__("train", force_mock=force_mock)
        self.config = config or {}

    def fetch(self) -> TrainBoardData:
        """
        获取并归一化列车数据。

        当前 Task 3 只实现了 mock 路径。
        huxley2 / transportapi 的 live 归一化尚未实现；
        live 路径由 TrainSourceBridge 显式 fallback 到旧 TrainProvider 处理，
        不应绕过 bridge 直接调用本方法。
        """
        data_source = self.config.get("data_source", "mock")
        if data_source == "mock":
            data = self._mock_data()
            self._cached_data = data
            return data
        raise NotImplementedError(
            f"TrainSource.fetch() only implements the mock path. "
            f"data_source='{data_source}' is not yet supported here. "
            f"Live paths (huxley2 / transportapi) are handled by "
            f"TrainSourceBridge via fallback to the legacy TrainProvider."
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
        )
