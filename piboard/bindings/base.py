"""
BaseBinding 抽象基类。

【静态脚手架 — 本轮未接入运行路径】

Task 3 将建立 Source → App slot 的具体映射，届时实现具体 Binding 子类。
"""
from abc import ABC, abstractmethod
from typing import Any


class BaseBinding(ABC):
    """绑定：将 Source 的原始数据转换并路由到 App 的特定 slot。"""

    source_id: str   # 数据来源的 Source ID
    app_slot: str    # 对应 App 内的 slot 名称

    @abstractmethod
    def transform(self, raw_data: Any) -> Any:
        """将 Source 原始数据转换为 App slot 期望的格式。"""
