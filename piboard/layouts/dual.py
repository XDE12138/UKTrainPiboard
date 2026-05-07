"""
双板布局：自动感知屏幕方向
  横屏（w > h）→ 左右各半，中间垂直 1px 分隔线
  竖屏（h > w）→ 上下各半，中间水平 1px 分隔线
"""
import pygame
from typing import List, Optional
from layouts.base import BaseLayout
from providers.base import BaseProvider
from board.board_renderer import BoardRenderer
from board.animations import AnimationController
from config import (
    TICKER_SPEED, PAGE_FLIP_INTERVAL, TRANSITION_DURATION, is_portrait,
    LOW_POWER_TICKER_PAGE_INTERVAL_MS,
)

DIVIDER_COLOR = (50, 35, 5)


class DualLayout(BaseLayout):

    layout_id = "dual"
    display_name = "Dual Board"
    slot_count = 2

    def __init__(self, colors: dict, animations_enabled: bool = True):
        super().__init__(colors, animations_enabled)
        self._renderer = BoardRenderer(colors)
        self._anims = [
            AnimationController(TICKER_SPEED, PAGE_FLIP_INTERVAL,
                                TRANSITION_DURATION, animations_enabled),
            AnimationController(TICKER_SPEED, PAGE_FLIP_INTERVAL,
                                TRANSITION_DURATION, animations_enabled),
        ]
        self._last_ids = ["", ""]
        self._last_tickers = ["", ""]
        self._ticker_page_starts = [0, 0]
        self._panel_widths = [0, 0]
        self._work_surfs = [None, None]

    def render(self, screen: pygame.Surface,
               providers: List[BaseProvider]) -> None:
        w, h = screen.get_size()
        portrait = is_portrait(w, h)

        if portrait:
            # 竖屏：上下分割
            half_h = h // 2
            panel_sizes = [(w, half_h - 1), (w, half_h - 1)]
            panel_positions = [(0, 0), (0, half_h + 1)]
        else:
            # 横屏：左右分割
            half_w = w // 2
            panel_sizes = [(half_w - 1, h), (half_w - 1, h)]
            panel_positions = [(0, 0), (half_w + 1, 0)]

        for i in range(2):
            panel_w, panel_h = panel_sizes[i]
            pos_x, pos_y = panel_positions[i]
            self._panel_widths[i] = panel_w
            provider = providers[i] if i < len(providers) else None

            if provider is None:
                surf = pygame.Surface((panel_w, panel_h))
                surf.fill((8, 8, 8))
                screen.blit(surf, (pos_x, pos_y))
                continue

            content = provider.get_content()
            anim = self._anims[i]

            if (self._work_surfs[i] is None or
                    self._work_surfs[i].get_size() != (panel_w, panel_h)):
                self._work_surfs[i] = pygame.Surface((panel_w, panel_h))

            ticker_text = content.ticker or ""
            if (content.provider_id != self._last_ids[i] or
                    ticker_text != self._last_tickers[i]):
                self._last_ids[i] = content.provider_id
                self._last_tickers[i] = ticker_text
                self._ticker_page_starts[i] = pygame.time.get_ticks()
                rows_h = self._renderer.get_rows_area_height(
                    panel_h, bool(content.ticker), content, panel_w)
                anim.set_content(content, area_h=rows_h)

            params = anim.update()
            self._renderer.render(
                self._work_surfs[i], content,
                ticker_offset=params["ticker_offset"],
                rows_scroll_offset=params["rows_scroll_offset"],
                ticker_page=(self._ticker_page(i)
                             if not self.animations_enabled else None),
            )
            screen.blit(self._work_surfs[i], (pos_x, pos_y))

        # 分隔线
        if portrait:
            half_h = h // 2
            pygame.draw.line(screen, DIVIDER_COLOR, (0, half_h), (w, half_h), 1)
        else:
            half_w = w // 2
            pygame.draw.line(screen, DIVIDER_COLOR, (half_w, 0), (half_w, h), 1)

    def on_providers_changed(self, providers: List[BaseProvider]):
        self._last_ids = ["", ""]
        self._last_tickers = ["", ""]
        self._ticker_page_starts = [0, 0]
        self._work_surfs = [None, None]
        for anim in self._anims:
            anim.ticker.reset()
            anim.page_flip.reset()

    def next_render_ms(self, providers: List[BaseProvider],
                       now_ms: int) -> Optional[int]:
        if self.animations_enabled:
            return None
        next_times = []
        for i, provider in enumerate(providers[:2]):
            w = self._panel_widths[i] if i < len(self._panel_widths) else 0
            if not w:
                continue
            content = provider.get_content()
            if not content.ticker:
                continue
            if self._renderer.ticker_page_count(content.ticker, w) <= 1:
                continue
            start = self._ticker_page_starts[i] or now_ms
            page = max(0, (now_ms - start) // LOW_POWER_TICKER_PAGE_INTERVAL_MS)
            next_times.append(
                start + (page + 1) * LOW_POWER_TICKER_PAGE_INTERVAL_MS
            )
        return min(next_times) if next_times else None

    def _ticker_page(self, idx: int) -> int:
        start = self._ticker_page_starts[idx]
        if not start:
            return 0
        elapsed = pygame.time.get_ticks() - start
        return max(0, elapsed // LOW_POWER_TICKER_PAGE_INTERVAL_MS)
