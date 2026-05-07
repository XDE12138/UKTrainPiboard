"""
板面渲染器：把 BoardContent 画到 pygame.Surface。

布局（从上到下，portrait-first）：
  顶部栏     6%   header_left / header_right       MEDIUM
  标题区    14%   title / subtitle / page_label     LARGE / SMALL
  内容行   余量   rows（左右两列，自动行高）          SMALL
  底部区    20%   carriage / operator / ticker / status
"""
import pygame
import datetime as _dt
from typing import Optional, Tuple
from board.content import BoardContent
from board.dot_font import (
    render_text, render_text_right_aligned, measure_text,
    FontSize
)


# ---------------------------------------------------------------------------
# 颜色解析
# ---------------------------------------------------------------------------
def _resolve_color(color_name: str, theme_colors: dict) -> Tuple[int, int, int]:
    return theme_colors.get(color_name, theme_colors.get("amber", (255, 149, 0)))


# ---------------------------------------------------------------------------
# 高亮行背景颜色
# ---------------------------------------------------------------------------
HIGHLIGHT_BG = (40, 28, 0, 110)  # 琥珀色透明背景（RGBA），强化首行层级感

# ---------------------------------------------------------------------------
# 渲染器主类
# ---------------------------------------------------------------------------
class BoardRenderer:
    """
    将一个 BoardContent 渲染到给定 Surface。

    可复用：每帧调用 render()，内部不持有任何状态（状态由 animations.py 管理）。
    ticker 滚动偏移量由外部（animations.py）传入。
    """

    def __init__(self, colors: dict):
        self.colors = colors
        self._substrate_cache: dict = {}  # {(w,h): pygame.Surface}

    # ------------------------------------------------------------------
    # 暗点阵底板（模拟未点亮 LED 矩阵）
    # ------------------------------------------------------------------

    def _get_substrate(self, w: int, h: int) -> pygame.Surface:
        key = (w, h)
        if key not in self._substrate_cache:
            surf = pygame.Surface((w, h))
            surf.fill((8, 8, 8))
            dot_color = (28, 16, 0)  # DOT_OFF
            for cy in range(1, h, 3):
                for cx in range(1, w, 3):
                    surf.set_at((cx, cy), dot_color)
            self._substrate_cache[key] = surf
        return self._substrate_cache[key]

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def render(self, surface: pygame.Surface, content: BoardContent,
               ticker_offset: int = 0,
               rows_scroll_offset: int = 0,
               ticker_page: Optional[int] = None) -> None:
        w, h = surface.get_size()

        # 暗点阵底板替代纯黑填充
        surface.blit(self._get_substrate(w, h), (0, 0))

        # 区域划分
        header_h = int(h * 0.08)   # 时间 + 站台行
        title_h  = int(h * 0.14)   # 目的地 + 副标题

        # footer 高度：Train Template 固定 25%，Info Template content-driven
        _tpl = self._resolve_template(content)
        if _tpl == "train":
            footer_h = int(h * 0.25)
        else:
            footer_h = self._info_footer_height(content)

        rows_h   = h - header_h - title_h - footer_h

        y_header = 0
        y_title  = header_h
        y_rows   = header_h + title_h
        y_footer = h - footer_h

        # 渲染各区域
        self._draw_header(surface, content, 0, y_header, w, header_h)
        self._draw_title(surface, content, 0, y_title, w, title_h)
        self._draw_rows(surface, content, 0, y_rows, w, rows_h, rows_scroll_offset)
        if footer_h > 0:
            self._draw_footer(surface, content, 0, y_footer, w, footer_h,
                              ticker_offset, ticker_page)

        # 顶层分隔线
        self._draw_separator(surface, y_title, w)
        self._draw_separator(surface, y_rows, w)
        if footer_h > 0:
            self._draw_separator(surface, y_footer, w)

    def get_rows_area_height(self, surface_h: int, has_ticker: bool = False,
                             content: "BoardContent | None" = None,
                             surface_w: int = 0,
                             ticker_page: Optional[int] = None) -> int:
        """返回内容行区域高度（供 animations.py 计算翻页）。"""
        header_h = int(surface_h * 0.08)
        title_h  = int(surface_h * 0.14)
        if content is not None and self._resolve_template(content) == "info":
            footer_h = self._info_footer_height(content)
        else:
            footer_h = int(surface_h * 0.25)
        _ = has_ticker, surface_w, ticker_page
        return surface_h - header_h - title_h - footer_h

    # ------------------------------------------------------------------
    # 模板解析与 Info footer 高度计算
    # ------------------------------------------------------------------

    def _resolve_template(self, content: "BoardContent") -> str:
        """解析实际使用的模板类型。"""
        if content.template == "train":
            return "train"
        if content.template == "info":
            return "info"
        # auto fallback: 有 carriage_hint 走 train，否则走 info
        return "train" if content.carriage_hint else "info"

    def _info_footer_height(self, content: "BoardContent") -> int:
        """Info Template 的 footer 高度：按实际需要的行数计算。"""
        _, SMALL_H = measure_text("A", FontSize.SMALL)
        row_h = SMALL_H + 6
        n = 0
        if content.ticker:      n += 1
        if content.footer:      n += 1
        if content.status_text: n += 1
        return n * row_h  # 可为 0

    # ------------------------------------------------------------------
    # 私有：各区域绘制
    # ------------------------------------------------------------------

    def _draw_header(self, surface, content, x, y, w, h):
        c = self.colors
        pad = 8
        _, char_h = measure_text("A", FontSize.MEDIUM)
        # 垂直居中对齐，参考图中时间和站台号均处于 header 区垂直中心
        mid_y = y + max(0, (h - char_h) // 2)

        header_left = self._resolve_header_text(
            content.header_left, content.header_left_clock_format)
        header_right = self._resolve_header_text(
            content.header_right, content.header_right_clock_format)

        if header_left:
            render_text(surface, header_left, x + pad, mid_y,
                        FontSize.MEDIUM, _resolve_color("amber", c))
        if header_right:
            render_text_right_aligned(surface, header_right,
                                      x + w - pad, mid_y,
                                      FontSize.MEDIUM, _resolve_color("amber", c))

    @staticmethod
    def _resolve_header_text(text: str, clock_format: Optional[str]) -> str:
        if not clock_format:
            return text
        return _dt.datetime.now().strftime(clock_format).upper()

    def _resolve_title_font(self, content, avail_w: int, pad: int) -> "FontSize":
        """
        解析 title 实际使用的字号（遵守字体冻结规则）。
        AUTO: 优先 XLARGE，超宽降级到 LARGE。
        title 渲染前必须 upper()，避免小写触发 5×7→7×9 fallback。
        """
        size_str = getattr(content, "title_size", "AUTO")
        raw_text = self._resolve_title_text(content)
        text = raw_text.upper() if raw_text else ""
        usable_w = avail_w - 2 * pad

        if size_str == "XLARGE":
            return FontSize.XLARGE
        if size_str == "LARGE":
            return FontSize.LARGE

        # AUTO: 优先 XLARGE
        xl_w, _ = measure_text(text, FontSize.XLARGE)
        if xl_w <= usable_w:
            return FontSize.XLARGE
        return FontSize.LARGE

    @staticmethod
    def _resolve_title_text(content) -> str:
        clock_format = getattr(content, "title_clock_format", None)
        if clock_format:
            return _dt.datetime.now().strftime(clock_format).upper()
        return content.title or ""

    def _draw_title(self, surface, content, x, y, w, h):
        c = self.colors
        pad = 8

        title_font = self._resolve_title_font(content, w, pad)
        _, title_char_h = measure_text("A", title_font)
        _, sub_char_h   = measure_text("A", FontSize.SMALL)

        PREF_TOP_PAD = 6
        PREF_GAP     = 4

        if content.subtitle:
            needed = title_char_h + PREF_GAP + sub_char_h
            avail  = h - PREF_TOP_PAD
            if avail >= needed:
                base_y = y + PREF_TOP_PAD
                gap = PREF_GAP
            else:
                gap = max(2, h - title_char_h - sub_char_h - 4)
                base_y = y + max(2, (h - title_char_h - gap - sub_char_h) // 2)
        else:
            base_y = y + PREF_TOP_PAD
            gap = PREF_GAP

        base_y = max(y + 2, base_y)

        title_raw = self._resolve_title_text(content)
        if title_raw:
            # LARGE / XLARGE 必须 uppercase
            title_text = title_raw.upper() if title_font in (FontSize.LARGE, FontSize.XLARGE) else title_raw
            render_text(surface, title_text, x + pad, base_y,
                        title_font,
                        _resolve_color(content.title_color, c))
        if content.subtitle:
            sub_y = base_y + title_char_h + gap
            render_text(surface, content.subtitle, x + pad, sub_y,
                        FontSize.SMALL,
                        _resolve_color(content.subtitle_color, c))
            # page_label 右对齐，与 subtitle 同行
            if content.page_label:
                render_text_right_aligned(surface, content.page_label,
                                          x + w - pad, sub_y,
                                          FontSize.SMALL,
                                          _resolve_color(content.subtitle_color, c))

    def _draw_rows(self, surface, content, x, y, w, h, scroll_offset):
        if not content.rows:
            return
        c = self.colors
        pad = 8

        _, char_h = measure_text("A", FontSize.SMALL)
        row_h = max(char_h + 6, h // max(len(content.rows), 1))
        row_h = min(row_h, 38)   # 上限：参考图行高约 35-38px

        clip_rect = pygame.Rect(x, y, w, h)
        old_clip = surface.get_clip()
        surface.set_clip(clip_rect)

        for i, row in enumerate(content.rows):
            ry = y + i * row_h - scroll_offset
            if ry + row_h < y or ry > y + h:
                continue
            if row.highlight:
                hl_surf = pygame.Surface((w, row_h), pygame.SRCALPHA)
                hl_surf.fill(HIGHLIGHT_BG)
                surface.blit(hl_surf, (x, ry))

            text_y = ry + (row_h - char_h) // 2
            indent = row.indent

            if row.left:
                render_text(surface, row.left, x + pad + indent, text_y,
                            FontSize.SMALL,
                            _resolve_color(row.left_color, c))
            if row.right:
                render_text_right_aligned(surface, row.right,
                                          x + w - pad, text_y,
                                          FontSize.SMALL,
                                          _resolve_color(row.right_color, c))

        surface.set_clip(old_clip)

    # ------------------------------------------------------------------
    # 底部区段：按模板分发
    # ------------------------------------------------------------------

    def _draw_footer(self, surface, content, x, y, w, h,
                     ticker_offset=0, ticker_page=None):
        tpl = self._resolve_template(content)
        if tpl == "train":
            self._draw_footer_train(surface, content, x, y, w, h,
                                    ticker_offset, ticker_page)
        else:
            self._draw_footer_info(surface, content, x, y, w, h,
                                   ticker_offset, ticker_page)

    # ------------------------------------------------------------------
    # Train Template footer：carriage → operator → ticker → status
    # ------------------------------------------------------------------

    def _draw_footer_train(self, surface, content, x, y, w, h,
                           ticker_offset=0, ticker_page=None):
        c = self.colors
        pad = 8
        _, SMALL_H = measure_text("A", FontSize.SMALL)

        # 四子区自适应分配（参考图：carriage ≈40%，operator ≈30%，status ≈30%）
        status_sub   = max(SMALL_H + 6, int(h * 0.26))
        ticker_sub   = max(SMALL_H + 6, int(h * 0.20)) if content.ticker else 0
        operator_sub = max(SMALL_H + 6, int(h * 0.26))
        carriage_sub = max(0, h - operator_sub - ticker_sub - status_sub)

        y_carriage = y
        y_operator = y + carriage_sub
        y_ticker   = y + carriage_sub + operator_sub
        y_status   = y + h - status_sub

        # 子区背景
        pygame.draw.rect(surface, (12, 8, 0), (x, y_operator, w, operator_sub))
        pygame.draw.rect(surface, (6, 12, 6), (x, y_status, w, status_sub))

        # 内部分隔线
        self._draw_separator(surface, y_operator, w)
        if content.ticker:
            self._draw_separator(surface, y_ticker, w)
        self._draw_separator(surface, y_status, w)

        # ---- carriage 车厢图 ----
        if content.carriage_hint and carriage_sub > 0:
            self._draw_carriage(surface, content.carriage_hint,
                                x, y_carriage, w, carriage_sub)

        # ---- operator 名称 ----
        char_h = SMALL_H
        op_mid_y = y_operator + (operator_sub - char_h) // 2
        if content.footer:
            render_text(surface, content.footer, x + pad, op_mid_y,
                        FontSize.SMALL,
                        _resolve_color(content.footer_color, c))

        # ---- ticker 跑马灯（倒数第二层） ----
        if content.ticker and ticker_sub > 0:
            self._draw_ticker(surface, content.ticker,
                              x, y_ticker, w, ticker_sub, ticker_offset,
                              ticker_page)

        # ---- status 绿色状态（最底层）----
        st_mid_y = y_status + (status_sub - char_h) // 2
        if content.status_text:
            render_text(surface, content.status_text, x + pad, st_mid_y,
                        FontSize.SMALL,
                        _resolve_color(content.status_color, c))

    # ------------------------------------------------------------------
    # Info Template footer：ticker → footer/source → status（紧凑，content-driven）
    # status 永远在最底部（结论行）
    # ------------------------------------------------------------------

    def _draw_footer_info(self, surface, content, x, y, w, _h,
                          ticker_offset=0, ticker_page=None):
        c = self.colors
        pad = 8
        _, SMALL_H = measure_text("A", FontSize.SMALL)
        row_h = SMALL_H + 6

        # 从上到下：ticker → footer → status（status 固定最底部）
        # 先确定每行的 y 坐标
        cur_y = y

        if content.ticker:
            self._draw_ticker(surface, content.ticker,
                              x, cur_y, w, row_h, ticker_offset,
                              ticker_page)
            cur_y += row_h
            self._draw_separator(surface, cur_y, w)

        if content.footer:
            pygame.draw.rect(surface, (12, 8, 0), (x, cur_y, w, row_h))
            mid_y = cur_y + (row_h - SMALL_H) // 2
            render_text(surface, content.footer, x + pad, mid_y,
                        FontSize.SMALL,
                        _resolve_color(content.footer_color, c))
            cur_y += row_h
            self._draw_separator(surface, cur_y, w)

        if content.status_text:
            pygame.draw.rect(surface, (6, 12, 6), (x, cur_y, w, row_h))
            mid_y = cur_y + (row_h - SMALL_H) // 2
            render_text(surface, content.status_text, x + pad, mid_y,
                        FontSize.SMALL,
                        _resolve_color(content.status_color, c))

    def _draw_carriage(self, surface, carriage_hint, x, y, w, h):
        """渲染车厢方块图。本轮仅支持 count 格式 "N"。"""
        try:
            n_coaches = int(carriage_hint.split(":")[0])
        except (ValueError, IndexError):
            return
        if n_coaches <= 0:
            return

        pad = 8
        box_h = max(8, min(int(h * 0.55), 22))
        box_gap = 1   # 参考图中车厢矩形几乎紧贴，1px 缝隙
        avail_w = w - 2 * pad
        box_w = min(24, (avail_w - box_gap * (n_coaches - 1)) // n_coaches)
        if box_w <= 0:
            return

        total_w = n_coaches * box_w + (n_coaches - 1) * box_gap
        start_x = x + (w - total_w) // 2
        box_y   = y + (h - box_h) // 2

        amber = self.colors.get("amber", (255, 149, 0))
        for i in range(n_coaches):
            bx = start_x + i * (box_w + box_gap)
            pygame.draw.rect(surface, amber, (bx, box_y, box_w, box_h), 1)

    def _draw_ticker(self, surface, text, x, y, w, h, offset,
                     ticker_page=None):
        c = self.colors
        _, char_h = measure_text("A", FontSize.SMALL)

        clip_rect = pygame.Rect(x, y, w, h)
        old_clip = surface.get_clip()
        surface.set_clip(clip_rect)

        if ticker_page is not None:
            pages = self.ticker_pages(text, w)
            page = pages[ticker_page % len(pages)]
            mid_y = y + (h - char_h) // 2
            render_text(surface, page, x + 8, mid_y,
                        FontSize.SMALL, _resolve_color("amber", c))
        else:
            mid_y = y + (h - char_h) // 2
            text_w, _ = measure_text(text, FontSize.SMALL)
            gap = 60
            tx = x - (offset % (text_w + gap))
            while tx < x + w:
                render_text(surface, text, tx, mid_y,
                            FontSize.SMALL, _resolve_color("amber", c))
                tx += text_w + gap

        surface.set_clip(old_clip)

    def ticker_page_count(self, text: str, w: int) -> int:
        return len(self.ticker_pages(text, w))

    def ticker_pages(self, text: str, w: int) -> list:
        """低功耗 ticker：保持单行，按可用宽度拆成分页片段。"""
        usable_w = max(1, w - 16)
        char_w, _ = measure_text("M", FontSize.SMALL)
        max_chars = max(1, usable_w // max(1, char_w))
        words = str(text).split()
        if not words:
            return [""]

        pages = []
        current = ""
        for word in words:
            while len(word) > max_chars:
                if current:
                    pages.append(current)
                    current = ""
                pages.append(word[:max_chars])
                word = word[max_chars:]
            if not word:
                continue

            candidate = word if not current else f"{current} {word}"
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current:
                pages.append(current)
                current = word

        if current:
            pages.append(current)

        return pages or [""]

    def _draw_separator(self, surface, y, w):
        sep_color = (65, 45, 8)
        pygame.draw.line(surface, sep_color, (0, y), (w, y), 1)
