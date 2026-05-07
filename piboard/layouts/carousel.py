"""轮播布局：多个 Provider 按设定间隔自动轮换，切换时有翻页动画。"""
import pygame
from typing import List, Optional
from layouts.base import BaseLayout
from providers.base import BaseProvider
from board.board_renderer import BoardRenderer
from board.animations import AnimationController, ContentTransitionAnimation
from config import (
    TICKER_SPEED, PAGE_FLIP_INTERVAL, TRANSITION_DURATION,
    LOW_POWER_TICKER_PAGE_INTERVAL_MS,
)

DEFAULT_CAROUSEL_INTERVAL = 10_000  # ms
LOW_POWER_CAROUSEL_INTERVAL = 60_000  # ms


class CarouselLayout(BaseLayout):

    layout_id = "carousel"
    display_name = "Carousel"
    slot_count = 3  # 最多3个槽位，但可少于3

    def __init__(self, colors: dict, animations_enabled: bool = True,
                 interval_ms: int = DEFAULT_CAROUSEL_INTERVAL,
                 low_power_interval_ms: int = LOW_POWER_CAROUSEL_INTERVAL):
        super().__init__(colors, animations_enabled)
        self._renderer = BoardRenderer(colors)
        self._anim = AnimationController(
            TICKER_SPEED, PAGE_FLIP_INTERVAL, TRANSITION_DURATION,
            animations_enabled,
        )
        self._transition = ContentTransitionAnimation(TRANSITION_DURATION)
        self._interval_ms = interval_ms
        self._low_power_interval_ms = low_power_interval_ms
        self._current_idx = 0
        self._last_switch = 0
        self._last_provider_id = ""
        self._last_ticker = ""
        self._last_surface_w = 0
        self._ticker_page_start = 0
        self._work_surf = None
        self._prev_surf = None

    def render(self, screen: pygame.Surface,
               providers: List[BaseProvider]) -> None:
        if not providers:
            screen.fill((8, 8, 8))
            return

        w, h = screen.get_size()
        self._last_surface_w = w
        now = pygame.time.get_ticks()

        if self._work_surf is None or self._work_surf.get_size() != (w, h):
            self._work_surf = pygame.Surface((w, h))

        # 自动轮换
        if self._last_switch == 0:
            self._last_switch = now

        interval_ms = self._effective_interval_ms()
        if now - self._last_switch >= interval_ms and len(providers) > 1:
            # 触发切换
            if self.animations_enabled:
                if self._prev_surf is None:
                    self._prev_surf = pygame.Surface((w, h))
                self._prev_surf.blit(self._work_surf, (0, 0))
                self._transition.trigger(self._prev_surf)
            self._current_idx = (self._current_idx + 1) % len(providers)
            self._last_switch = now
            self._last_provider_id = ""

        provider = providers[self._current_idx % len(providers)]
        content = provider.get_content()

        ticker_text = content.ticker or ""
        if content.provider_id != self._last_provider_id or ticker_text != self._last_ticker:
            self._last_provider_id = content.provider_id
            self._last_ticker = ticker_text
            self._ticker_page_start = now
            rows_h = self._renderer.get_rows_area_height(
                h, bool(content.ticker), content, w)
            self._anim.set_content(content, area_h=rows_h)

        params = self._anim.update()
        self._renderer.render(
            self._work_surf, content,
            ticker_offset=params["ticker_offset"],
            rows_scroll_offset=params["rows_scroll_offset"],
            ticker_page=self._ticker_page() if not self.animations_enabled else None,
        )

        # 合成过渡动画
        if self._transition.is_active:
            self._transition.update(self._work_surf, screen)
        else:
            screen.blit(self._work_surf, (0, 0))

    def on_providers_changed(self, providers: List[BaseProvider]):
        self._current_idx = 0
        self._last_switch = 0
        self._last_provider_id = ""
        self._last_ticker = ""
        self._ticker_page_start = 0
        self._anim.ticker.reset()
        self._anim.page_flip.reset()

    def next_render_ms(self, providers: List[BaseProvider],
                       now_ms: int) -> Optional[int]:
        """低功耗模式下定时唤醒一帧，用于静态翻到下一块内容。"""
        if self.animations_enabled:
            return None
        next_times = []
        if len(providers) > 1:
            if self._last_switch == 0:
                next_times.append(now_ms)
            else:
                next_times.append(self._last_switch + self._effective_interval_ms())

        if providers and self._last_surface_w:
            provider = providers[self._current_idx % len(providers)]
            content = provider.get_content()
            if (content.ticker and
                    self._renderer.ticker_page_count(
                        content.ticker, self._last_surface_w) > 1):
                start = self._ticker_page_start or now_ms
                page = max(0, (now_ms - start) //
                           LOW_POWER_TICKER_PAGE_INTERVAL_MS)
                next_times.append(
                    start + (page + 1) * LOW_POWER_TICKER_PAGE_INTERVAL_MS
                )

        return min(next_times) if next_times else None

    def _effective_interval_ms(self) -> int:
        if self.animations_enabled:
            return self._interval_ms
        return self._low_power_interval_ms

    def _ticker_page(self) -> int:
        if not self._ticker_page_start:
            return 0
        elapsed = pygame.time.get_ticks() - self._ticker_page_start
        return max(0, elapsed // LOW_POWER_TICKER_PAGE_INTERVAL_MS)
