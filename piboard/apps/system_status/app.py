"""
SystemStatusApp — Task 8 proof-of-switch 第二 App。

设计原则：
- 极轻量：静态文字，无 Provider，无 Layout，无动画
- 与展示看板共享点阵字体、间距和状态颜色
- is_animating() 始终返回 False → 激活后降至 FPS_IDLE（1fps）
- on_state_changed() 为空操作：此 app 没有 layout 系统，忽略所有设置变化

用途：验证 ScreenHost 的 runtime app switching 链路，不是产品化 dashboard。
"""
import pygame
import logging
from board.board_renderer import BoardRenderer
from board.content import BoardContent, BoardRow
from config import COLORS
from state import app_state
from apps.base import BaseApp

log = logging.getLogger(__name__)

class SystemStatusApp(BaseApp):
    """超轻量第二 App，专为 Task 8 runtime switching 验证而设计。"""

    def __init__(self):
        self._surfaces: list = []   # [(pygame.Surface, (x, y)), ...]
        self._surface_size = None

    # ------------------------------------------------------------------
    # BaseApp interface
    # ------------------------------------------------------------------

    def on_activate(self):
        """切换到此 app 时调用；构建文字 surfaces 并标脏。"""
        self._surface_size = None
        app_state.set_dirty(True)
        log.info("SystemStatusApp activated")

    def on_deactivate(self):
        """离开此 app 时调用；无需清理。"""
        log.info("SystemStatusApp deactivated")

    def on_state_changed(self, layout_id: str, slots: list, settings: dict) -> None:
        """此 app 没有 layout 系统；忽略所有 state 变化。"""

    def is_animating(self) -> bool:
        """无动画 → 渲染后降至 FPS_IDLE（1 fps），不占用 CPU。"""
        return False

    def render(self, screen: pygame.Surface, dt: float) -> None:
        if self._surface_size != screen.get_size():
            self._build_surfaces(screen.get_size())
        for surf, pos in self._surfaces:
            screen.blit(surf, pos)

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _build_surfaces(self, size):
        """预渲染所有文字 surfaces，居中布局。"""
        surface = pygame.Surface(size)
        BoardRenderer(COLORS).render(surface, BoardContent(
            header_left="SYSTEM", header_right="PIBOARD", title="STATUS",
            subtitle="DISPLAY RUNTIME",
            rows=[BoardRow("RUNTIME", "ACTIVE", highlight=True),
                  BoardRow("DISPLAY", "STATIC"),
                  BoardRow("CONTROL", "WEB CONSOLE")],
            footer="PIBOARD", status_text="READY", status_color="green",
            template="info"))
        self._surfaces = [(surface, (0, 0))]
        self._surface_size = size
