"""
UKStationApp：将现有 layouts/ + providers/ 渲染体系包装为 BaseApp。

本轮是薄包装层：
- board/ / layouts/ / providers/ 内部逻辑完全不动。
- on_state_changed() 直接移植自 Renderer._switch_layout()，行为等价。
- is_animating() 修正了 Renderer._is_animating() 的缺陷：
    原实现只检测 hasattr(layout, '_anim')，DualLayout 用 _anims 列表
    未被覆盖，CarouselLayout 的独立 _transition 也未被覆盖。
    本实现正确区分三种 layout。
"""
import pygame
import logging
import time
from typing import Dict, List, Optional
from apps.base import BaseApp
from layouts.base import BaseLayout
from providers.base import BaseProvider
from config import COLOR_THEMES, COLORS

log = logging.getLogger(__name__)


def _check_anim_controller(anim) -> bool:
    """检测一个 AnimationController 是否有活跃动画。"""
    if not getattr(anim, "enabled", True):
        return False
    if anim.ticker._running:
        return True
    if anim.page_flip._flipping:
        return True
    if anim.transition.is_active:
        return True
    return False


class UKStationApp(BaseApp):

    def __init__(
        self,
        layouts: Dict[str, BaseLayout],
        providers: Dict[str, BaseProvider],
        initial_layout: str,
        initial_slots: List[str],
        initial_app_settings: dict,
    ):
        # 只保存 class 引用，实例由 on_state_changed() 按需重建
        # （与原 Renderer._switch_layout() 的行为保持一致）
        self._layout_classes: Dict[str, type] = {
            lid: type(l) for lid, l in layouts.items()
        }
        self._providers: Dict[str, BaseProvider] = providers
        self._current_layout: BaseLayout = None
        self._current_slots: List[str] = []
        self._next_clock_render_ms: Optional[int] = None

        # 用初始状态完成第一次 layout 建立
        self.on_state_changed(initial_layout, initial_slots, initial_app_settings)

    # ------------------------------------------------------------------
    # BaseApp 接口
    # ------------------------------------------------------------------

    def render(self, screen: pygame.Surface, dt: float) -> None:
        if self._current_layout is None:
            screen.fill((8, 8, 8))
            return
        providers = self._active_providers()
        self._current_layout.render(screen, providers)
        self._schedule_next_clock_render(providers)

    def is_animating(self) -> bool:
        """
        区分三种 layout 的动画属性：

        SingleLayout  → _anim (AnimationController)，无 _anims，无独立 _transition
        DualLayout    → _anims (list of AnimationController)，无 _anim
        CarouselLayout → _anim (AnimationController) + 独立 _transition
                         (ContentTransitionAnimation，负责 provider 切换过渡)

        检测顺序：_anims 优先（DualLayout），其次 _transition（CarouselLayout），
        最后 _anim（SingleLayout）。
        """
        layout = self._current_layout
        if layout is None:
            return False

        # DualLayout：_anims 列表
        if hasattr(layout, '_anims'):
            return any(_check_anim_controller(a) for a in layout._anims)

        # CarouselLayout：_anim + 独立 _transition
        if hasattr(layout, '_transition'):
            anim_active = (_check_anim_controller(layout._anim)
                           if hasattr(layout, '_anim') else False)
            return anim_active or layout._transition.is_active

        # SingleLayout：只有 _anim
        if hasattr(layout, '_anim'):
            return _check_anim_controller(layout._anim)

        return False

    def next_render_ms(self, now_ms: int) -> Optional[int]:
        """让支持低频动态的 layout 在 animations=false 时唤醒 Host。"""
        if self._current_layout is None:
            return None

        providers = self._active_providers()
        next_times = []
        layout_next = self._current_layout.next_render_ms(providers, now_ms)
        if layout_next is not None:
            next_times.append(layout_next)

        if self._has_render_clock(providers):
            if self._next_clock_render_ms is None:
                self._schedule_next_clock_render(providers, now_ms)
            if self._next_clock_render_ms is not None:
                next_times.append(self._next_clock_render_ms)
        else:
            self._next_clock_render_ms = None

        return min(next_times) if next_times else None

    def on_state_changed(self, layout_id: str, slots: List[str],
                         app_settings: dict) -> None:
        """
        移植自 Renderer._switch_layout()，行为完全等价：
        重建 layout 实例以应用新颜色 / 动画设置，并注入当前 providers。

        app_settings 仅含 app 级键（color_theme, animations_enabled），
        不包含 device_settings（brightness, orientation）。
        """
        colors = COLOR_THEMES.get(app_settings.get("color_theme", "amber"), COLORS)
        anim_enabled = app_settings.get("animations_enabled", True)

        LayoutClass = self._layout_classes.get(layout_id)
        if LayoutClass is None:
            log.warning(f"Layout '{layout_id}' not found, fallback to single")
            LayoutClass = self._layout_classes.get("single")
        if LayoutClass is None:
            log.error("No layouts registered, cannot render")
            return

        new_layout = LayoutClass(colors=colors, animations_enabled=anim_enabled)
        providers = [self._providers[s] for s in slots
                     if s in self._providers]
        new_layout.on_providers_changed(providers)

        self._current_layout = new_layout
        self._current_slots = list(slots)
        self._next_clock_render_ms = None
        log.info(f"UKStationApp: layout='{layout_id}', slots={slots}")

    def _active_providers(self) -> List[BaseProvider]:
        return [self._providers[s] for s in self._current_slots
                if s in self._providers]

    def _has_render_clock(self, providers: List[BaseProvider]) -> bool:
        for provider in providers:
            content = provider.get_content()
            if (getattr(content, "header_left_clock_format", None)
                    or getattr(content, "header_right_clock_format", None)
                    or getattr(content, "title_clock_format", None)):
                return True
        return False

    def _schedule_next_clock_render(self, providers: List[BaseProvider],
                                    now_ms: Optional[int] = None):
        if not self._has_render_clock(providers):
            self._next_clock_render_ms = None
            return

        if now_ms is None:
            now_ms = pygame.time.get_ticks()
        seconds_to_next_minute = 60.0 - (time.time() % 60.0)
        delay_ms = max(250, int(seconds_to_next_minute * 1000))
        self._next_clock_render_ms = now_ms + delay_ms
