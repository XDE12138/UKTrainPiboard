"""单板全屏布局：一个 Provider 内容撑满整个屏幕。"""
import pygame
from typing import List, Optional
from layouts.base import BaseLayout
from providers.base import BaseProvider
from board.board_renderer import BoardRenderer
from board.animations import AnimationController
from config import (
    TICKER_SPEED, PAGE_FLIP_INTERVAL, TRANSITION_DURATION,
    LOW_POWER_TICKER_PAGE_INTERVAL_MS,
)


class SingleLayout(BaseLayout):

    layout_id = "single"
    display_name = "Single Board"
    slot_count = 1

    def __init__(self, colors: dict, animations_enabled: bool = True):
        super().__init__(colors, animations_enabled)
        self._renderer = BoardRenderer(colors)
        self._anim = AnimationController(
            ticker_speed=TICKER_SPEED,
            page_interval=PAGE_FLIP_INTERVAL,
            transition_ms=TRANSITION_DURATION,
            enabled=animations_enabled,
        )
        self._last_provider_id: str = ""
        self._last_ticker: str = ""
        self._last_surface_w: int = 0
        self._ticker_page_start: int = 0
        self._work_surf: pygame.Surface = None

    def render(self, screen: pygame.Surface,
               providers: List[BaseProvider]) -> None:
        w, h = screen.get_size()
        self._last_surface_w = w

        # 懒初始化工作 Surface
        if self._work_surf is None or self._work_surf.get_size() != (w, h):
            self._work_surf = pygame.Surface((w, h))

        if not providers:
            screen.fill((8, 8, 8))
            return

        provider = providers[0]
        content = provider.get_content()

        # 检测 Provider 切换，触发过渡动画
        ticker_text = content.ticker or ""
        provider_changed = content.provider_id != self._last_provider_id
        ticker_changed = ticker_text != self._last_ticker
        if provider_changed or ticker_changed:
            if provider_changed and self._last_provider_id:
                self._anim.trigger_transition(screen)
            self._last_provider_id = content.provider_id
            self._last_ticker = ticker_text
            self._ticker_page_start = pygame.time.get_ticks()

            # 重置动画参数
            rows_h = self._renderer.get_rows_area_height(
                h, bool(content.ticker), content, w)
            self._anim.set_content(content, area_h=rows_h)

        # 更新动画
        anim_params = self._anim.update()

        # 渲染到工作 Surface
        self._renderer.render(
            self._work_surf, content,
            ticker_offset=anim_params["ticker_offset"],
            rows_scroll_offset=anim_params["rows_scroll_offset"],
            ticker_page=self._ticker_page() if not self.animations_enabled else None,
        )

        # 合成过渡动画（如有）
        if self._anim.transition.is_active:
            self._anim.transition.update(self._work_surf, screen)
        else:
            screen.blit(self._work_surf, (0, 0))

    def on_providers_changed(self, providers: List[BaseProvider]):
        self._last_provider_id = ""
        self._last_ticker = ""
        self._ticker_page_start = 0
        self._anim.ticker.reset()
        self._anim.page_flip.reset()

    def next_render_ms(self, providers: List[BaseProvider],
                       now_ms: int) -> Optional[int]:
        if self.animations_enabled or not providers or not self._last_surface_w:
            return None
        content = providers[0].get_content()
        if not content.ticker:
            return None
        if self._renderer.ticker_page_count(content.ticker, self._last_surface_w) <= 1:
            return None
        start = self._ticker_page_start or now_ms
        page = max(0, (now_ms - start) // LOW_POWER_TICKER_PAGE_INTERVAL_MS)
        return start + (page + 1) * LOW_POWER_TICKER_PAGE_INTERVAL_MS

    def _ticker_page(self) -> int:
        if not self._ticker_page_start:
            return 0
        elapsed = pygame.time.get_ticks() - self._ticker_page_start
        return max(0, elapsed // LOW_POWER_TICKER_PAGE_INTERVAL_MS)
