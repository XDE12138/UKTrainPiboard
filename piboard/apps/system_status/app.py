"""
SystemStatusApp — Task 8 proof-of-switch 第二 App。

设计原则：
- 极轻量：静态文字，无 Provider，无 Layout，无动画
- 视觉上与 uk_station（琥珀色点阵）明显不同：白字黑底
- is_animating() 始终返回 False → 激活后降至 FPS_IDLE（1fps）
- on_state_changed() 为空操作：此 app 没有 layout 系统，忽略所有设置变化

用途：验证 ScreenHost 的 runtime app switching 链路，不是产品化 dashboard。
"""
import pygame
import logging
from state import app_state
from apps.base import BaseApp

log = logging.getLogger(__name__)

# 颜色
_WHITE  = (220, 220, 220)
_GREY   = (140, 140, 140)
_DIM    = ( 80,  80,  80)
_BLACK  = (  0,   0,   0)

# 文字内容（静态）
_LINES = [
    ("[ SYSTEM STATUS ]",     "large",  _WHITE),
    ("App: system_status",    "medium", _GREY),
    ("PiBoard multi-app runtime", "small", _DIM),
    ("Switch via web console", "small",  _DIM),
]


class SystemStatusApp(BaseApp):
    """超轻量第二 App，专为 Task 8 runtime switching 验证而设计。"""

    def __init__(self):
        self._surfaces: list = []   # [(pygame.Surface, (x, y)), ...]
        self._built = False

    # ------------------------------------------------------------------
    # BaseApp interface
    # ------------------------------------------------------------------

    def on_activate(self):
        """切换到此 app 时调用；构建文字 surfaces 并标脏。"""
        self._build_surfaces()
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
        screen.fill(_BLACK)
        for surf, pos in self._surfaces:
            screen.blit(surf, pos)

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _build_surfaces(self):
        """预渲染所有文字 surfaces，居中布局。"""
        try:
            w = pygame.display.get_surface().get_width()
            h = pygame.display.get_surface().get_height()
        except Exception:
            w, h = 1024, 600

        size_map = {"large": 36, "medium": 22, "small": 16}

        rendered = []
        for text, size_key, color in _LINES:
            font_size = size_map.get(size_key, 18)
            try:
                font = pygame.font.SysFont("monospace", font_size)
            except Exception:
                font = pygame.font.Font(None, font_size)
            surf = font.render(text, True, color)
            rendered.append(surf)

        # 垂直居中：总高度 = 所有行高 + 行间距
        line_gap = 14
        total_h = sum(s.get_height() for s in rendered) + line_gap * (len(rendered) - 1)
        y = (h - total_h) // 2

        self._surfaces = []
        for surf in rendered:
            x = (w - surf.get_width()) // 2
            self._surfaces.append((surf, (x, y)))
            y += surf.get_height() + line_gap

        self._built = True
