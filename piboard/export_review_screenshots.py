"""
Task 12 审核图导出脚本（v4.3-fix）。
用途：生成 portrait-first 静态 PNG 供人工审核，不接入主流程。

不依赖 git；before 效果通过内联原始参数的 BeforeRenderer 模拟。

证据边界说明：
  - before/after 对照图（B 组）证明的是 **布局/结构** 变化
    （区段比例、底部四子区拆分、subtitle/page_label 拆分、substrate 暗点阵 等）。
  - BeforeRenderer 仍然调用当前 dot_font.py（radius=max(2,...)），
    因此 before 图的 dot 形状与 after 相同，**不能** 用于证明 dot 圆形质感的改善。
  - dot 圆形质感的证据来自 D 组 zoom 图（after-only），
    这些图证明当前版本的 dot 是圆形而非方块，但不提供与旧版 radius=1 的严格对照。

用法：
  python3 export_review_screenshots.py

输出目录：piboard/review_artifacts/task12/
"""
import os
import sys

# 无头模式运行，不弹窗口
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.dirname(__file__))

import pygame
pygame.display.init()
pygame.display.set_mode((1, 1))  # dummy window

from board.board_renderer import BoardRenderer
from board.content import BoardContent, BoardRow
from board.dot_font import (
    render_text as _render_text,
    render_text_right_aligned as _render_text_right_aligned,
    measure_text as _measure_text,
    FontSize,
)
from providers.mock import MockProvider
from config import COLORS

# ---------------------------------------------------------------------------
# 输出目录
# ---------------------------------------------------------------------------
OUT_DIR = os.path.join(os.path.dirname(__file__), "review_artifacts", "task12")
os.makedirs(OUT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Dense fixture（固定数据，before/after 完全相同，不依赖 mock.py）
# ---------------------------------------------------------------------------
DENSE_FIXTURE = BoardContent(
    header_left="11:42",
    header_right="Platform 7",
    title="Kings Lynn via",
    title_color="amber",
    subtitle="Calling at:",
    subtitle_color="dim",
    page_label="Page 1 of 1",
    rows=[
        BoardRow("Cambridge",       "(12:30)", highlight=True),
        BoardRow("Cambridge North", "(12:39)"),
        BoardRow("Waterbeach",      "(12:44)"),
        BoardRow("Ely",             "(12:53)"),
        BoardRow("Littleport",      "(13:03)"),
        BoardRow("Downham Market",  "(13:15)"),
        BoardRow("Watlington",      "(13:21)"),
        BoardRow("& Kings Lynn",    "(13:30)"),
    ],
    footer="Great Northern",
    footer_color="dim",
    status_text="On time",
    status_color="green",
    ticker="Great Northern service. This train is formed of 8 coaches.",
    carriage_hint="8",
    provider_id="dense-fixture",
)


# ---------------------------------------------------------------------------
# BeforeRenderer：内联 v3 原始布局参数，用于生成 before 对照图
#
# 此 renderer 仅还原 v3 的 **布局常量**（区段比例、纯黑背景、footer 结构），
# 不还原 v3 的 dot 渲染（radius=1 方块）。dot_font.py 已全局改为 radius=max(2,...),
# 因此 before 图与 after 图在 dot 形状上完全相同。
#
# 结论：before/after 对照 **仅** 证明布局/结构变化，不证明 dot 质感改善。
# ---------------------------------------------------------------------------
def _resolve_color(color_name, theme_colors):
    return theme_colors.get(color_name, theme_colors.get("amber", (255, 149, 0)))


class BeforeRenderer:
    """用 v3 的原始常量渲染，仅用于生成审核 before 图。"""

    def __init__(self, colors):
        self.colors = colors

    def render(self, surface, content, ticker_offset=0, rows_scroll_offset=0):
        w, h = surface.get_size()
        surface.fill((8, 8, 8))  # v3: 纯黑，无 substrate

        # ---- v3 区域比例 ----
        header_h = int(h * 0.10)
        title_h  = int(h * 0.14)
        ticker_h = int(h * 0.08) if content.ticker else 0
        footer_h = int(h * 0.09)
        rows_h   = h - header_h - title_h - footer_h - ticker_h

        y_header = 0
        y_title  = header_h
        y_rows   = header_h + title_h
        y_footer = h - footer_h - ticker_h
        y_ticker = h - ticker_h

        self._draw_header(surface, content, 0, y_header, w, header_h)
        self._draw_title(surface, content, 0, y_title, w, title_h)
        self._draw_rows(surface, content, 0, y_rows, w, rows_h, rows_scroll_offset)
        self._draw_footer(surface, content, 0, y_footer, w, footer_h)
        if content.ticker:
            self._draw_ticker(surface, content.ticker, 0, y_ticker, w, ticker_h, ticker_offset)

        self._draw_separator(surface, y_title, w)
        self._draw_separator(surface, y_footer, w)
        if content.ticker:
            self._draw_separator(surface, y_ticker, w)

    def _draw_header(self, surface, content, x, y, w, h):
        c = self.colors
        pad = 8
        mid_y = y + 4  # v3: 贴顶 4px
        if content.header_left:
            _render_text(surface, content.header_left, x + pad, mid_y,
                         FontSize.MEDIUM, _resolve_color("amber", c))
        if content.header_right:
            _render_text_right_aligned(surface, content.header_right,
                                       x + w - pad, mid_y,
                                       FontSize.MEDIUM, _resolve_color("dim", c))

    def _draw_title(self, surface, content, x, y, w, h):
        c = self.colors
        pad = 8
        _, title_h = _measure_text("A", FontSize.LARGE)
        _, sub_h   = _measure_text("A", FontSize.SMALL)
        PREF_TOP_PAD = 6
        PREF_GAP = 6

        if content.subtitle:
            needed = title_h + PREF_GAP + sub_h
            avail  = h - PREF_TOP_PAD
            if avail >= needed:
                base_y = y + PREF_TOP_PAD
                gap = PREF_GAP
            else:
                gap = max(2, h - title_h - sub_h - 4)
                base_y = y + max(2, (h - title_h - gap - sub_h) // 2)
        else:
            base_y = y + PREF_TOP_PAD
            gap = PREF_GAP
        base_y = max(y + 2, base_y)

        if content.title:
            _render_text(surface, content.title, x + pad, base_y,
                         FontSize.LARGE, _resolve_color(content.title_color, c))
        if content.subtitle:
            # v3: subtitle 包含 page info 作为一体字符串
            sub_text = content.subtitle
            if content.page_label:
                sub_text = content.subtitle + "  " + content.page_label
            _render_text(surface, sub_text, x + pad, base_y + title_h + gap,
                         FontSize.SMALL, _resolve_color(content.subtitle_color, c))

    def _draw_rows(self, surface, content, x, y, w, h, scroll_offset):
        if not content.rows:
            return
        c = self.colors
        pad = 8
        _, char_h = _measure_text("A", FontSize.SMALL)
        row_h = max(char_h + 4, h // max(len(content.rows), 1))
        row_h = min(row_h, 28)

        clip_rect = pygame.Rect(x, y, w, h)
        old_clip = surface.get_clip()
        surface.set_clip(clip_rect)

        for i, row in enumerate(content.rows):
            ry = y + i * row_h - scroll_offset
            if ry + row_h < y or ry > y + h:
                continue
            if row.highlight:
                hl_surf = pygame.Surface((w, row_h), pygame.SRCALPHA)
                hl_surf.fill((40, 28, 0, 110))
                surface.blit(hl_surf, (x, ry))
            text_y = ry + (row_h - char_h) // 2
            indent = row.indent
            if row.left:
                _render_text(surface, row.left, x + pad + indent, text_y,
                             FontSize.SMALL, _resolve_color(row.left_color, c))
            if row.right:
                _render_text_right_aligned(surface, row.right,
                                           x + w - pad, text_y,
                                           FontSize.SMALL,
                                           _resolve_color(row.right_color, c))

        surface.set_clip(old_clip)

    def _draw_footer(self, surface, content, x, y, w, h):
        c = self.colors
        pad = 8
        # v3: 单层 footer（operator + status 同行）
        pygame.draw.rect(surface, (12, 8, 0), (x, y, w, h))
        _, char_h = _measure_text("A", FontSize.SMALL)
        mid_y = y + (h - char_h) // 2
        if content.footer:
            _render_text(surface, content.footer, x + pad, mid_y,
                         FontSize.SMALL, _resolve_color(content.footer_color, c))
        if content.status_text:
            _render_text_right_aligned(surface, content.status_text,
                                       x + w - pad, mid_y,
                                       FontSize.SMALL,
                                       _resolve_color(content.status_color, c))

    def _draw_ticker(self, surface, text, x, y, w, h, offset):
        pass  # 静态审核不需要 ticker 滚动

    def _draw_separator(self, surface, y, w):
        pygame.draw.line(surface, (65, 45, 8), (0, y), (w, y), 1)


# ---------------------------------------------------------------------------
# 渲染并保存
# ---------------------------------------------------------------------------
def render_to_png(renderer, content, path, width=600, height=1024):
    surf = pygame.Surface((width, height))
    renderer.render(surf, content, ticker_offset=0, rows_scroll_offset=0)
    pygame.image.save(surf, path)
    print(f"  saved: {path}")
    return surf  # 返回 surface 供 zoom 截取


def save_zoom_crop(surface, rect, scale, path):
    """从 surface 截取 rect 区域，放大 scale 倍后保存。"""
    # 确保 rect 在 surface 范围内
    sw, sh = surface.get_size()
    r = pygame.Rect(rect)
    r.clamp_ip(pygame.Rect(0, 0, sw, sh))
    if r.w <= 0 or r.h <= 0:
        print(f"  SKIP zoom (empty crop): {path}")
        return
    sub = surface.subsurface(r)
    zoomed = pygame.transform.scale(sub, (r.w * scale, r.h * scale))
    pygame.image.save(zoomed, path)
    print(f"  saved zoom: {path}")


def main():
    after_renderer  = BoardRenderer(COLORS)
    before_renderer = BeforeRenderer(COLORS)

    mock = MockProvider()
    weather  = mock._weather_preset()
    calendar = mock._calendar_preset()
    train    = mock._train_preset()

    print(f"\n=== Exporting screenshots -> {OUT_DIR} ===\n")

    # ---- A. 主审核图（portrait 600x1024）----
    print("--- A. Main review (portrait) ---")
    main_surf = render_to_png(after_renderer, train,
                              os.path.join(OUT_DIR, "portrait-after-train-main.png"))
    render_to_png(after_renderer, train,
                  os.path.join(OUT_DIR, "portrait-after-train-close-check.png"))

    # ---- B. 严格视觉对照（same dense fixture, before vs after）----
    print("\n--- B. Dense fixture before/after (portrait) ---")
    render_to_png(before_renderer, DENSE_FIXTURE,
                  os.path.join(OUT_DIR, "portrait-before-dense-fixture.png"))
    render_to_png(after_renderer, DENSE_FIXTURE,
                  os.path.join(OUT_DIR, "portrait-after-dense-fixture.png"))

    # ---- C. 安全验证（half-height）----
    print("\n--- C. Half-height safety (portrait) ---")
    render_to_png(after_renderer, DENSE_FIXTURE,
                  os.path.join(OUT_DIR, "portrait-after-half-height.png"),
                  width=600, height=511)

    # ---- D. Dot 质感验证（zoom crops from main_surf）----
    print("\n--- D. Dot quality zoom ---")
    # main_surf is 600x1024, after_renderer proportions:
    # header_h = int(1024 * 0.06) = 61
    # title_h  = int(1024 * 0.14) = 143
    # y_title  = 61, y_rows = 61 + 143 = 204

    # D1: LARGE title chars "Kin" at (8, 61+6) = (8, 67), ~110x50px
    save_zoom_crop(main_surf, (6, 65, 115, 50), 4,
                   os.path.join(OUT_DIR, "dot-zoom-large.png"))

    # D2: MEDIUM header chars "11:4" at (8, 4), ~85x30px
    save_zoom_crop(main_surf, (6, 2, 90, 32), 4,
                   os.path.join(OUT_DIR, "dot-zoom-medium.png"))

    # D3: SMALL single stop name at rows area, first row at y=204, ~100x28px
    save_zoom_crop(main_surf, (6, 204, 110, 28), 4,
                   os.path.join(OUT_DIR, "dot-zoom-small-single.png"))

    # D4: SMALL full stops line (entire width) at first row
    save_zoom_crop(main_surf, (0, 204, 600, 28), 4,
                   os.path.join(OUT_DIR, "dot-zoom-small-line.png"))

    # ---- E. 横屏不破版确认 ----
    print("\n--- E. Landscape no-break check ---")
    render_to_png(after_renderer, weather,
                  os.path.join(OUT_DIR, "landscape-after-weather.png"),
                  width=1024, height=600)
    render_to_png(after_renderer, calendar,
                  os.path.join(OUT_DIR, "landscape-after-calendar.png"),
                  width=1024, height=600)

    print("\nDone.")


if __name__ == "__main__":
    main()
