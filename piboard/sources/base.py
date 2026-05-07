"""
BaseSource 抽象基类。

【静态脚手架 — 本轮未接入运行路径】

现有 providers/ 继续直接使用，不受此文件影响。
Task 3 将把现有 Provider 包装为具体 Source 子类并接入 UKStationApp。

force_mock 字段预留统一 mock 开关接口，解决现有各 Provider 独立判定
mock 的不一致问题（见审计结论 1）。Task 4 负责实现统一策略。
"""
from abc import ABC, abstractmethod
from typing import Any


class BaseSource(ABC):
    """数据源抽象：从外部获取数据，缓存供主线程安全读取。"""

    def __init__(self, source_id: str, force_mock: bool = False):
        self.source_id = source_id
        # 统一 mock 开关，Task 4 实现。本轮只预留字段，不接入任何判断逻辑。
        self.force_mock = force_mock
        self._cached_data: Any = None

    @abstractmethod
    def fetch(self) -> Any:
        """在后台线程中调用，从外部获取原始数据。不得调用 pygame。"""

    def get_data(self) -> Any:
        """主线程安全，返回最近一次 fetch() 结果的缓存。"""
        return self._cached_data
