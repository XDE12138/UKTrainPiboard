"""
Typography Test Board — PiBoard CC-UK-TR
=========================================
独立运行的字体系统测试页。目标：一次性暴露字体和排版问题，
不依赖 Flask / 数据 Provider / 主 board renderer。

运行方式：
    cd piboard
    python typography_board.py

键盘：
    Q / ESC     退出
    UP / DOWN   滚动
    PAGE UP/DN  翻页
    HOME / END  顶部 / 底部

测试内容覆盖：
    [1]  字号层级总览（XLARGE / LARGE / MEDIUM / SMALL）
    [2]  大时间显示 XLARGE（数字宽度一致性 / colon 对齐）
    [3]  状态词汇（LARGE + MEDIUM）
    [4]  数字密集内容（MEDIUM）
    [5]  出发行模拟（SMALL）
    [6]  完整字符集（SMALL）
    [7]  易混字符对比（MEDIUM）
    [8]  LARGE/XLARGE lowercase 拉伸失真演示
    [9]  Descender 专项测试（含 baseline 参考线）
    [10] Colon 垂直对齐测试（XLARGE + MEDIUM）
    [11] Ticker 静态预览（SMALL）
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pygame
from board.dot_font import FontSize, render_text, measure_text
from config import COLORS, BG_COLOR

# ── 颜色 ──────────────────────────────────────────────────────────────────────
AMBER     = COLORS["amber"]    # (255, 149, 0)
DIM       = COLORS["dim"]      # (160, 100, 5)
GREEN     = COLORS["green"]    # (80, 220, 80)
RED       = COLORS["red"]      # (220, 50, 50)
ORANGE    = COLORS["orange"]   # (255, 160, 30)

SEP_COLOR      = (65,  45,  8)    # 分隔线
REF_CAP        = (90,  35,  0)    # 参考线：cap height 底边（当前 baseline）
REF_XHEIGHT    = (50,  20,  0)    # 参考线：x-height 顶边（虚线）
REF_MID        = (70,  30,  0)    # 参考线：字符垂直中点

# ── 布局常量 ──────────────────────────────────────────────────────────────────
SCREEN_W   = 1024
SCREEN_H   = 600
PAD_X      = 16
CANVAS_H   = 4000    # 足够容纳所有内容，最后按实际截断


# ─────────────────────────────────────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────────────────────────────────────

def draw_section_label(surf: pygame.Surface, text: str, y: int) -> int:
    """绘制 section 标题，返回标题底部 y。"""
    render_text(surf, text, PAD_X, y, FontSize.SMALL, DIM)
    _, h = measure_text(text, FontSize.SMALL)
    return y + h + 4


def draw_sep(surf: pygame.Surface, y: int) -> int:
    """绘制水平分隔线，返回分隔线下方 y（含间距）。"""
    pygame.draw.line(surf, SEP_COLOR, (PAD_X, y), (SCREEN_W - PAD_X, y), 1)
    return y + 10


def draw_ref_lines(surf: pygame.Surface, x: int, y: int,
                   size: str, width: int) -> None:
    """
    绘制 baseline / x-height 观察参考线。
    基于 measure_text 实际尺寸，不做抽象推算。

    橙色实线  — 字符顶边（top edge）
    暗红实线  — 字符底边（cap height / 当前 baseline）
    暗绿虚线  — 估算 x-height 顶边（仅 5×7 SMALL/MEDIUM 有意义）
                原理：5×7 小写字母通常 row 0-1 为空白，内容从 row 2 开始，
                      即 x-height top ≈ top + 2 × (char_h // 7)

    注：这些线仅供目视判断，不是精确 typographic 度量系统。
    """
    _, char_h = measure_text("H", size)
    right = x + width

    # cap height 底边（当前渲染 baseline）
    pygame.draw.line(surf, REF_CAP, (x, y + char_h), (right, y + char_h), 1)

    # x-height 顶边估算（仅 SMALL / MEDIUM）
    if size in (FontSize.SMALL, FontSize.MEDIUM):
        row_h = char_h // 7           # 每行像素高度（取整）
        x_top = y + 2 * row_h        # row 2 起始位置
        px = x
        while px < right:
            pygame.draw.line(surf, REF_XHEIGHT, (px, x_top), (min(px + 2, right), x_top), 1)
            px += 4


def draw_mid_line(surf: pygame.Surface, x: int, y: int,
                  size: str, width: int) -> None:
    """绘制字符高度垂直中点参考线（用于 colon 对齐测试）。"""
    _, char_h = measure_text("0", size)
    mid = y + char_h // 2
    right = x + width
    px = x
    while px < right:
        pygame.draw.line(surf, REF_MID, (px, mid), (min(px + 3, right), mid), 1)
        px += 6


# ─────────────────────────────────────────────────────────────────────────────
# 构建测试板（返回 Surface 和实际内容高度）
# ─────────────────────────────────────────────────────────────────────────────

def build_board() -> tuple:
    canvas = pygame.Surface((SCREEN_W, CANVAS_H), pygame.SRCALPHA)
    canvas.fill(BG_COLOR)

    _, sm_h = measure_text("H", FontSize.SMALL)
    _, md_h = measure_text("H", FontSize.MEDIUM)
    _, lg_h = measure_text("H", FontSize.LARGE)
    _, xl_h = measure_text("H", FontSize.XLARGE)

    y = 14

    # ── 页面标题 ─────────────────────────────────────────────────────────────
    render_text(canvas, "TYPOGRAPHY TEST BOARD", PAD_X, y, FontSize.MEDIUM, AMBER)
    hint = "Q:quit  UP/DN:scroll"
    hint_w, _ = measure_text(hint, FontSize.SMALL)
    render_text(canvas, hint, SCREEN_W - PAD_X - hint_w, y + (md_h - sm_h) // 2,
                FontSize.SMALL, DIM)
    y += md_h + 8
    y = draw_sep(canvas, y)

    # ── [1] 字号层级总览 ─────────────────────────────────────────────────────
    y = draw_section_label(canvas, "[ 1 ]  SIZE SCALE — XLARGE / LARGE / MEDIUM / SMALL", y)

    scale_items = [
        (FontSize.XLARGE, "XL", xl_h),
        (FontSize.LARGE,  "LG", lg_h),
        (FontSize.MEDIUM, "MD", md_h),
        (FontSize.SMALL,  "SM", sm_h),
    ]
    label_col_w, _ = measure_text("XL ", FontSize.SMALL)
    for size, lbl, ch in scale_items:
        render_text(canvas, lbl, PAD_X, y + max(0, (ch - sm_h) // 2),
                    FontSize.SMALL, DIM)
        render_text(canvas, "09:30  BOARDING  ON TIME", PAD_X + label_col_w + 4, y,
                    size, AMBER)
        y += ch + 6

    y += 4
    y = draw_sep(canvas, y)

    # ── [2] 大时间显示 XLARGE ─────────────────────────────────────────────────
    y = draw_section_label(canvas,
        "[ 2 ]  TIME HERO — XLARGE  (digit width / colon alignment)", y)

    times_xl = ["09:30", "14:15", "23:59", "00:00"]
    # 并排：计算每组宽度
    spacing_xl = 20
    tx = PAD_X
    for t in times_xl:
        render_text(canvas, t, tx, y, FontSize.XLARGE, AMBER)
        tw, _ = measure_text(t, FontSize.XLARGE)
        tx += tw + spacing_xl
    y += xl_h + 8

    y += 4
    y = draw_sep(canvas, y)

    # ── [3] 状态词汇 ─────────────────────────────────────────────────────────
    y = draw_section_label(canvas, "[ 3 ]  STATUS VOCABULARY — LARGE + MEDIUM", y)

    # LARGE 状态词，2列2行
    status_large = ["ON TIME", "DELAYED", "CANCELLED", "BOARDING"]
    col_split = SCREEN_W // 2
    for i, word in enumerate(status_large):
        col_x = PAD_X + (i % 2) * col_split
        row_y = y + (i // 2) * (lg_h + 6)
        render_text(canvas, word, col_x, row_y, FontSize.LARGE, AMBER)
    y += lg_h * 2 + 6 + 8

    # MEDIUM 状态词，单行
    status_med = ["NEXT: 09:00", "RAIN LIKELY", "3 DUE TODAY", "PLAT 4"]
    mx = PAD_X
    for word in status_med:
        render_text(canvas, word, mx, y, FontSize.MEDIUM, ORANGE)
        ww, _ = measure_text(word, FontSize.MEDIUM)
        gap_w, _ = measure_text("   ", FontSize.MEDIUM)
        mx += ww + gap_w
    y += md_h + 8

    y = draw_sep(canvas, y)

    # ── [4] 数字密集内容 MEDIUM ───────────────────────────────────────────────
    y = draw_section_label(canvas, "[ 4 ]  NUMBER DENSITY — MEDIUM", y)

    density_items = ["18°C", "72%", "09:30", "PLAT 4", "3 DUE TODAY",
                     "NEXT: 17:30", "0°C", "100%", "23:59"]
    dx = PAD_X
    dy = y
    gap_w, _ = measure_text("  ", FontSize.MEDIUM)
    for item in density_items:
        iw, _ = measure_text(item, FontSize.MEDIUM)
        if dx + iw > SCREEN_W - PAD_X:
            dx = PAD_X
            dy += md_h + 4
        render_text(canvas, item, dx, dy, FontSize.MEDIUM, AMBER)
        dx += iw + gap_w
    y = dy + md_h + 10

    y = draw_sep(canvas, y)

    # ── [5] 出发行模拟 SMALL ──────────────────────────────────────────────────
    y = draw_section_label(canvas, "[ 5 ]  DEPARTURE ROW SIMULATION — SMALL", y)

    rows_data = [
        ("09:30", "LONDON PADDINGTON",      "ON TIME",      GREEN),
        ("10:15", "BRISTOL TEMPLE MEADS",   "PLAT 2",       GREEN),
        ("14:00", "BIRMINGHAM NEW ST",      "DELAYED 8 MIN",RED),
        ("22:47", "MANCHESTER PICCADILLY",  "CANCELLED",    RED),
    ]
    time_col  = PAD_X
    dest_col  = PAD_X + 80
    stat_col  = SCREEN_W - PAD_X

    for i, (t, dest, stat, color) in enumerate(rows_data):
        ry = y + i * (sm_h + 5)
        # 首行高亮背景
        if i == 0:
            hl = pygame.Surface((SCREEN_W - 2 * PAD_X, sm_h + 4), pygame.SRCALPHA)
            hl.fill((40, 28, 0, 110))
            canvas.blit(hl, (PAD_X, ry - 2))
        render_text(canvas, t,    time_col, ry, FontSize.SMALL, AMBER)
        render_text(canvas, dest, dest_col, ry, FontSize.SMALL, AMBER)
        sw, _ = measure_text(stat, FontSize.SMALL)
        render_text(canvas, stat, stat_col - sw, ry, FontSize.SMALL, color)

    y += len(rows_data) * (sm_h + 5) + 4
    y = draw_sep(canvas, y)

    # ── [6] 完整字符集 SMALL ──────────────────────────────────────────────────
    y = draw_section_label(canvas, "[ 6 ]  FULL CHARACTER SET — SMALL", y)

    char_lines = [
        ("UPPERCASE", "ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
        ("lowercase", "abcdefghijklmnopqrstuvwxyz"),
        ("digits   ", "0 1 2 3 4 5 6 7 8 9"),
        ("symbols  ", ": - / . % ° ! ? ( ) , ' \" _ + = @ # &"),
    ]
    label_w, _ = measure_text("lowercase ", FontSize.SMALL)
    for lbl, chars in char_lines:
        render_text(canvas, lbl, PAD_X, y, FontSize.SMALL, DIM)
        render_text(canvas, chars, PAD_X + label_w, y, FontSize.SMALL, AMBER)
        y += sm_h + 4

    y += 4
    y = draw_sep(canvas, y)

    # ── [7] 易混字符对比 MEDIUM ───────────────────────────────────────────────
    y = draw_section_label(canvas, "[ 7 ]  AMBIGUOUS CHARACTERS — MEDIUM", y)

    pairs = [
        ("O vs 0", "O  0"),
        ("I l 1",  "I  l  1"),
        ("M N",    "M  N"),
        ("W V",    "W  V"),
        ("8 B",    "8  B"),
        ("S 5",    "S  5"),
    ]
    pair_col_w = (SCREEN_W - 2 * PAD_X) // len(pairs)
    for i, (lbl, chars) in enumerate(pairs):
        px = PAD_X + i * pair_col_w
        render_text(canvas, lbl,   px, y,               FontSize.SMALL,  DIM)
        render_text(canvas, chars, px, y + sm_h + 2,    FontSize.MEDIUM, AMBER)

    y += sm_h + 2 + md_h + 10
    y = draw_sep(canvas, y)

    # ── [8] LARGE/XLARGE lowercase 失真演示 ──────────────────────────────────
    y = draw_section_label(canvas,
        "[ 8 ]  LARGE/XLARGE LOWERCASE — stretch-fallback distortion", y)

    y = draw_section_label(canvas,
        "  lowercase at LARGE  (5x7 stretched to 7x9 — distorted, shown in red):", y)
    render_text(canvas, "partly cloudy", PAD_X, y, FontSize.LARGE, RED)
    y += lg_h + 6

    y = draw_section_label(canvas,
        "  UPPERCASE at LARGE  (native 7x9 bitmap — correct):", y)
    render_text(canvas, "PARTLY CLOUDY", PAD_X, y, FontSize.LARGE, AMBER)
    y += lg_h + 6

    y = draw_section_label(canvas,
        "  lowercase at XLARGE (distorted):", y)
    render_text(canvas, "humidity", PAD_X, y, FontSize.XLARGE, RED)
    y += xl_h + 6

    y = draw_section_label(canvas,
        "  RULE: LARGE + XLARGE must use UPPERCASE ONLY until _FONT_7X9 a-z is defined.", y)

    y = draw_sep(canvas, y)

    # ── [9] Descender 专项测试 ────────────────────────────────────────────────
    y = draw_section_label(canvas,
        "[ 9 ]  DESCENDER TEST — ref lines: solid=cap-bottom  dashed=x-height-top", y)
    y = draw_section_label(canvas,
        "  (lines are for observation only — not a precision measurement system)", y)

    # 9a: 下伸部字母单行
    desc_chars = "g   y   p   q   j"
    draw_ref_lines(canvas, PAD_X, y, FontSize.SMALL,
                   measure_text(desc_chars, FontSize.SMALL)[0] + 8)
    render_text(canvas, desc_chars, PAD_X, y, FontSize.SMALL, AMBER)
    render_text(canvas, "<-- descenders",
                PAD_X + measure_text(desc_chars, FontSize.SMALL)[0] + 20,
                y, FontSize.SMALL, DIM)
    y += sm_h + 10

    # 9b: 非下伸对比
    norm_chars = "x   a   e   n   h"
    draw_ref_lines(canvas, PAD_X, y, FontSize.SMALL,
                   measure_text(norm_chars, FontSize.SMALL)[0] + 8)
    render_text(canvas, norm_chars, PAD_X, y, FontSize.SMALL, AMBER)
    render_text(canvas, "<-- non-descenders (ref)",
                PAD_X + measure_text(norm_chars, FontSize.SMALL)[0] + 20,
                y, FontSize.SMALL, DIM)
    y += sm_h + 10

    # 9c: 单词测试（每行带参考线）
    desc_words = [
        "gypsy", "typography", "queue", "playing",
        "partly cloudy", "humidity", "today",
    ]
    for word in desc_words:
        ww, _ = measure_text(word, FontSize.SMALL)
        draw_ref_lines(canvas, PAD_X, y, FontSize.SMALL, ww + 8)
        render_text(canvas, word, PAD_X, y, FontSize.SMALL, AMBER)
        # 同行右侧显示大写对比
        uw, _ = measure_text(word.upper(), FontSize.SMALL)
        render_text(canvas, word.upper(), SCREEN_W // 2, y, FontSize.SMALL, DIM)
        y += sm_h + 7

    y += 4
    y = draw_section_label(canvas, "  Mixed: digit / uppercase / descender in same line:", y)

    mixed_lines = [
        "09:30 gy",
        "18°C / humidity",
        "due by 17:30",
        "09:30 typography",
        "NEXT: partly cloudy",
        "DELAYED · humidity 72%",
    ]
    for line in mixed_lines:
        lw, _ = measure_text(line, FontSize.SMALL)
        draw_ref_lines(canvas, PAD_X, y, FontSize.SMALL, lw + 8)
        render_text(canvas, line, PAD_X, y, FontSize.SMALL, AMBER)
        y += sm_h + 7

    y += 4
    y = draw_sep(canvas, y)

    # ── [10] Colon 垂直对齐测试 ───────────────────────────────────────────────
    y = draw_section_label(canvas,
        "[ 10 ] COLON ALIGNMENT — XLARGE + MEDIUM  (dashed = digit vertical midpoint)", y)

    for size, lbl10, ch10 in [
        (FontSize.XLARGE, "XL", xl_h),
        (FontSize.MEDIUM, "MD", md_h),
    ]:
        render_text(canvas, lbl10, PAD_X, y + (ch10 - sm_h) // 2, FontSize.SMALL, DIM)
        lbl_w, _ = measure_text(lbl10, FontSize.SMALL)
        tx = PAD_X + lbl_w + 12

        # 先画中点参考线覆盖整个时间区
        row_span = 3 * (measure_text("09:30", size)[0] + 24)
        draw_mid_line(canvas, tx, y, size, row_span)

        for t in ["09:30", "14:15", "00:00"]:
            render_text(canvas, t, tx, y, size, AMBER)
            tw, _ = measure_text(t, size)
            tx += tw + 24

        y += ch10 + 10

    y = draw_sep(canvas, y)

    # ── [11] Ticker 静态预览 ──────────────────────────────────────────────────
    y = draw_section_label(canvas, "[ 11 ] TICKER — static preview (SMALL)", y)

    ticker = ("Next departure 09:30 London Paddington platform 4  ·  On time  ·  "
              "Operator: Great Western Railway  ·  "
              "Today: partly cloudy 18°C humidity 72%  ·")

    # 截断到屏幕可见宽度
    visible = ""
    max_w = SCREEN_W - 2 * PAD_X
    for ch in ticker:
        tw, _ = measure_text(visible + ch, FontSize.SMALL)
        if tw > max_w:
            break
        visible += ch

    render_text(canvas, visible, PAD_X, y, FontSize.SMALL, DIM)
    y += sm_h + 16

    return canvas, y


# ─────────────────────────────────────────────────────────────────────────────
# 主循环
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("PiBoard — Typography Test Board")
    clock = pygame.time.Clock()

    board_surf, total_h = build_board()
    scroll_y   = 0
    max_scroll = max(0, total_h - SCREEN_H)
    step       = 36    # 单次滚动量（px）

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_q, pygame.K_ESCAPE):
                    running = False
                elif event.key == pygame.K_DOWN:
                    scroll_y = min(scroll_y + step, max_scroll)
                elif event.key == pygame.K_UP:
                    scroll_y = max(scroll_y - step, 0)
                elif event.key == pygame.K_PAGEDOWN:
                    scroll_y = min(scroll_y + SCREEN_H, max_scroll)
                elif event.key == pygame.K_PAGEUP:
                    scroll_y = max(scroll_y - SCREEN_H, 0)
                elif event.key == pygame.K_HOME:
                    scroll_y = 0
                elif event.key == pygame.K_END:
                    scroll_y = max_scroll
            elif event.type == pygame.MOUSEWHEEL:
                scroll_y = max(0, min(scroll_y - event.y * step, max_scroll))

        screen.fill(BG_COLOR)
        screen.blit(board_surf, (0, -scroll_y))

        # 滚动条
        if max_scroll > 0:
            bar_h = max(20, SCREEN_H * SCREEN_H // max(total_h, 1))
            bar_y = int(scroll_y / max_scroll * (SCREEN_H - bar_h))
            pygame.draw.rect(screen, (65, 45, 8), (SCREEN_W - 5, 0, 5, SCREEN_H))
            pygame.draw.rect(screen, AMBER,       (SCREEN_W - 5, bar_y, 5, bar_h))

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()


if __name__ == "__main__":
    main()
