"""Layout 抽象基类"""
from abc import ABC, abstractmethod
import pygame
from typing import Dict, List, Optional
from providers.base import BaseProvider


class BaseLayout(ABC):

    layout_id: str = "base"
    display_name: str = "Base Layout"

    # 该布局需要的 Provider 槽位数量
    slot_count: int = 1

    def __init__(self, colors: dict, animations_enabled: bool = True):
        self.colors = colors
        self.animations_enabled = animations_enabled

    @abstractmethod
    def render(self, screen: pygame.Surface,
               providers: List[BaseProvider]) -> None:
        """
        将 providers 列表中的内容渲染到 screen。
        providers 长度应与 slot_count 匹配。
        """
        ...

    def on_providers_changed(self, providers: List[BaseProvider]):
        """Provider 列表变更时调用（可选 override）。"""
        pass

    def next_render_ms(self, providers: List[BaseProvider],
                       now_ms: int) -> Optional[int]:
        """返回下一次低频渲染 tick；静态 layout 默认不主动唤醒。"""
        _ = providers, now_ms
        return None
