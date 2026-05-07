"""
动画系统：跑马灯、翻页、板面切换。

所有动画基于 pygame.time.get_ticks()，不使用 time.sleep()。
外部（renderer.py）每帧调用 update()，再读取各动画参数传给 BoardRenderer。
"""
import pygame
from typing import Optional
from board.content import BoardContent
from board.dot_font import measure_text, FontSize


class TickerAnimation:
    """跑马灯：文字从右向左匀速滚动，循环播放。"""

    def __init__(self, speed_px_per_sec: float = 60.0):
        self.speed = speed_px_per_sec
        self._offset: float = 0.0
        self._text: str = ""
        self._text_w: int = 0
        self._gap: int = 60
        self._last_ticks: int = 0
        self._running: bool = False

    def set_text(self, text: Optional[str]):
        if text and text != self._text:
            self._text = text
            self._text_w, _ = measure_text(text, FontSize.SMALL)
            self._offset = 0.0
        self._running = bool(text)

    def update(self) -> int:
        """返回当前偏移量（像素）。"""
        if not self._running:
            return 0
        now = pygame.time.get_ticks()
        if self._last_ticks == 0:
            self._last_ticks = now
        dt = (now - self._last_ticks) / 1000.0
        self._last_ticks = now
        cycle = self._text_w + self._gap
        if cycle > 0:
            self._offset = (self._offset + self.speed * dt) % cycle
        return int(self._offset)

    def reset(self):
        self._offset = 0.0
        self._last_ticks = 0


class PageFlipAnimation:
    """
    内容行翻页：rows 超出显示区时，每隔 interval 秒向上滑动翻一页。
    """

    def __init__(self, interval_sec: float = 8.0,
                 flip_duration_ms: int = 400):
        self.interval_ms = int(interval_sec * 1000)
        self.flip_duration = flip_duration_ms
        self._rows_count: int = 0
        self._visible_rows: int = 0
        self._page: int = 0
        self._total_pages: int = 1
        self._flip_start: int = 0
        self._flipping: bool = False
        self._last_page_time: int = 0
        self._row_height: int = 24   # px，与 board_renderer 中 row_h 一致

    def configure(self, rows_count: int, area_h: int, row_h: int):
        """每次 content 更新时调用。"""
        self._row_height = max(row_h, 1)
        self._rows_count = rows_count
        self._visible_rows = max(1, area_h // row_h)
        self._total_pages = max(
            1, (rows_count + self._visible_rows - 1) // self._visible_rows
        )
        self._page = 0
        self._flipping = False
        self._last_page_time = pygame.time.get_ticks()

    def update(self) -> int:
        """返回当前 rows 区域纵向滚动偏移（像素）。"""
        now = pygame.time.get_ticks()

        # 只有超过一页才翻
        if self._total_pages <= 1:
            return 0

        # 触发翻页
        if not self._flipping and now - self._last_page_time > self.interval_ms:
            self._page = (self._page + 1) % self._total_pages
            self._flip_start = now
            self._flipping = True
            self._last_page_time = now

        # 翻页动画中：线性插值
        if self._flipping:
            elapsed = now - self._flip_start
            if elapsed >= self.flip_duration:
                self._flipping = False
                return self._page * self._visible_rows * self._row_height
            else:
                progress = elapsed / self.flip_duration
                # ease-in-out
                t = progress * progress * (3 - 2 * progress)
                prev_page = (self._page - 1) % self._total_pages
                from_offset = prev_page * self._visible_rows * self._row_height
                to_offset   = self._page * self._visible_rows * self._row_height
                return int(from_offset + (to_offset - from_offset) * t)

        return self._page * self._visible_rows * self._row_height

    def reset(self):
        self._page = 0
        self._flipping = False
        self._last_page_time = pygame.time.get_ticks()


class ContentTransitionAnimation:
    """
    板面内容切换动画：旧内容上滑淡出，新内容从下淡入。
    """

    def __init__(self, duration_ms: int = 500):
        self.duration = duration_ms
        self._start: int = 0
        self._active: bool = False
        self._old_surface: Optional[pygame.Surface] = None

    def trigger(self, old_surface: pygame.Surface):
        """触发切换动画，传入旧画面的 Surface 副本。"""
        self._old_surface = old_surface.copy()
        self._start = pygame.time.get_ticks()
        self._active = True

    def update(self, new_surface: pygame.Surface,
               target: pygame.Surface) -> bool:
        """
        将过渡动画合成到 target。
        返回 True 表示动画仍在进行，False 表示已完成。
        """
        if not self._active:
            target.blit(new_surface, (0, 0))
            return False

        now = pygame.time.get_ticks()
        elapsed = now - self._start
        if elapsed >= self.duration:
            self._active = False
            target.blit(new_surface, (0, 0))
            return False

        progress = elapsed / self.duration
        t = progress * progress * (3 - 2 * progress)  # ease-in-out

        h = target.get_height()
        slide = int(h * t)
        alpha_new = int(255 * t)
        alpha_old = int(255 * (1 - t))

        # 旧画面上移 + 淡出
        if self._old_surface:
            old = self._old_surface.copy()
            old.set_alpha(alpha_old)
            target.blit(old, (0, -slide))

        # 新画面从下上移 + 淡入
        new_copy = new_surface.copy()
        new_copy.set_alpha(alpha_new)
        target.blit(new_copy, (0, h - slide))

        return True

    @property
    def is_active(self) -> bool:
        return self._active


class AnimationController:
    """
    汇总所有动画，提供统一接口。
    renderer.py 每帧调用一次 update()，获取渲染所需参数。
    """

    def __init__(self,
                 ticker_speed: float = 60.0,
                 page_interval: float = 8.0,
                 transition_ms: int = 500,
                 enabled: bool = True):
        self.enabled = enabled
        self.ticker = TickerAnimation(speed_px_per_sec=ticker_speed)
        self.page_flip = PageFlipAnimation(interval_sec=page_interval,
                                           flip_duration_ms=400)
        self.transition = ContentTransitionAnimation(duration_ms=transition_ms)

    def set_content(self, content: BoardContent,
                    area_h: int, row_h: int = 24):
        """每次内容切换时调用，重置相关动画。"""
        self.ticker.set_text(content.ticker)
        self.page_flip.configure(
            rows_count=len(content.rows),
            area_h=area_h,
            row_h=row_h,
        )

    def update(self) -> dict:
        """
        返回字典，供 BoardRenderer.render() 使用：
          ticker_offset, rows_scroll_offset
        """
        if not self.enabled:
            return {"ticker_offset": 0, "rows_scroll_offset": 0}
        return {
            "ticker_offset":      self.ticker.update(),
            "rows_scroll_offset": self.page_flip.update(),
        }

    def trigger_transition(self, old_surface: pygame.Surface):
        if self.enabled:
            self.transition.trigger(old_surface)
