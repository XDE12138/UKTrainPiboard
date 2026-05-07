"""BaseApp 抽象基类：定义所有 App 必须实现的接口。"""
from abc import ABC, abstractmethod
from typing import Optional
import pygame


class BaseApp(ABC):

    @abstractmethod
    def render(self, screen: pygame.Surface, dt: float) -> None:
        """渲染一帧到 screen。dt 为距上一帧的秒数。"""

    @abstractmethod
    def is_animating(self) -> bool:
        """是否有正在运行的动画（影响 ScreenHost 的 FPS 节流策略）。"""

    def next_render_ms(self, now_ms: int) -> Optional[int]:
        """返回下一次低频渲染的 pygame tick 时间；None 表示无需定时唤醒。"""
        return None

    def on_activate(self) -> None:
        """切换到此 App 时由 ScreenHost 调用。"""

    def on_deactivate(self) -> None:
        """离开此 App 时由 ScreenHost 调用。"""

    def on_state_changed(self, layout_id: str, slots: list,
                         settings: dict) -> None:
        """
        app_state 中 layout / slots / settings 发生变化时由 ScreenHost 调用。
        App 负责根据新状态重建内部 layout 实例并注入正确的 providers。
        """
