"""
DEPRECATED: 此文件已被 host/host.py + apps/uk_station/app.py 替代。
main.py 不再实例化 Renderer，保留此文件仅供回归对照，确认无问题后可删除。

pygame 主渲染循环。

性能策略：
- dirty=False 时降至 1fps，CPU < 3%
- dirty=True 时以 FPS_ACTIVE(30fps) 渲染
- 渲染完成后立即 set_dirty(False)
"""
import pygame
import logging
from typing import Dict, List
from state import app_state
from config import FPS_ACTIVE, FPS_IDLE, COLORS, COLOR_THEMES
from layouts.base import BaseLayout
from providers.base import BaseProvider

log = logging.getLogger(__name__)


class Renderer:

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self._clock = pygame.time.Clock()
        self._layouts: Dict[str, BaseLayout] = {}
        self._providers: Dict[str, BaseProvider] = {}
        self._current_layout: BaseLayout = None
        self._current_slots: List[str] = []
        self._running = False

    # ------------------------------------------------------------------
    # 注册
    # ------------------------------------------------------------------

    def register_layout(self, layout: BaseLayout):
        self._layouts[layout.layout_id] = layout

    def register_provider(self, provider: BaseProvider):
        self._providers[provider.provider_id] = provider

    # ------------------------------------------------------------------
    # 主循环
    # ------------------------------------------------------------------

    def run(self):
        self._running = True
        app_state.set_dirty(True)

        while self._running:
            # 处理事件
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self._running = False

            # 检查状态变更
            dirty = app_state.dirty
            layout_id = app_state.current_layout
            slots = app_state.layout_slots
            settings = app_state.settings

            # 切换布局或 Provider
            if (layout_id != getattr(self._current_layout, 'layout_id', None)
                    or slots != self._current_slots):
                self._switch_layout(layout_id, slots, settings)
                dirty = True

            # 渲染
            if dirty or self._is_animating():
                self._render(settings)
                app_state.set_dirty(False)
                self._clock.tick(FPS_ACTIVE)
            else:
                self._clock.tick(FPS_IDLE)

        pygame.quit()
        log.info("Renderer stopped")

    def stop(self):
        self._running = False

    # ------------------------------------------------------------------
    # 私有
    # ------------------------------------------------------------------

    def _switch_layout(self, layout_id: str, slots: List[str],
                       settings: dict):
        colors = COLOR_THEMES.get(settings.get("color_theme", "amber"), COLORS)
        anim_enabled = settings.get("animations_enabled", True)

        layout = self._layouts.get(layout_id)
        if layout is None:
            log.warning(f"Layout '{layout_id}' not found, fallback to single")
            layout = self._layouts.get("single")
        if layout is None:
            return

        # 重建布局实例（以应用新颜色/动画设置）
        LayoutClass = type(layout)
        new_layout = LayoutClass(colors=colors, animations_enabled=anim_enabled)

        providers = [self._providers[s] for s in slots
                     if s in self._providers]
        new_layout.on_providers_changed(providers)

        self._current_layout = new_layout
        self._current_slots = list(slots)
        log.info(f"Switched to layout '{layout_id}', slots={slots}")

    def _render(self, settings: dict):
        if self._current_layout is None:
            self.screen.fill((8, 8, 8))
            pygame.display.flip()
            return

        providers = [self._providers[s] for s in self._current_slots
                     if s in self._providers]
        self._current_layout.render(self.screen, providers)
        pygame.display.flip()

    def _is_animating(self) -> bool:
        """检测是否有正在运行的动画（跑马灯、过渡）。"""
        layout = self._current_layout
        if layout is None:
            return False
        # SingleLayout / DualLayout 均有 _anim 属性
        if hasattr(layout, '_anim'):
            anim = layout._anim
            if anim.ticker._running:
                return True
            if anim.transition.is_active:
                return True
            if anim.page_flip._flipping:
                return True
        return False
