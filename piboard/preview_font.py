"""
字体预览脚本：在窗口中展示各尺寸点阵字体效果。
运行：python3 preview_font.py
按 Q 或关闭窗口退出。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pygame
from board.dot_font import (
    render_text, measure_text, FontSize, DOT_OFF
)
from config import COLORS, BG_COLOR

WIDTH, HEIGHT = 1024, 600

def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("PiBoard — Dot Font Preview")
    clock = pygame.time.Clock()

    amber = COLORS["amber"]
    green = COLORS["green"]
    dim   = COLORS["dim"]
    white = COLORS["white"]
    red   = COLORS["red"]

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_q:
                running = False

        screen.fill(BG_COLOR)

        y = 10
        # ---- SMALL ----
        render_text(screen, "SMALL: ABCDEFGHIJKLMNOPQRSTUVWXYZ", 10, y, FontSize.SMALL, amber)
        y += 30
        render_text(screen, "SMALL: abcdefghijklmnopqrstuvwxyz", 10, y, FontSize.SMALL, amber)
        y += 30
        render_text(screen, "SMALL: 0123456789 :.,!?-+/", 10, y, FontSize.SMALL, amber)
        y += 40

        # ---- MEDIUM ----
        render_text(screen, "MEDIUM: Platform 9  On time  14:35", 10, y, FontSize.MEDIUM, green)
        y += 50
        render_text(screen, "MEDIUM: Newcastle  12:35", 10, y, FontSize.MEDIUM, white)
        y += 55

        # ---- LARGE (7x9) ----
        render_text(screen, "LARGE: Edinburgh", 10, y, FontSize.LARGE, amber)
        y += 65

        # ---- XLARGE (7x9 big) ----
        render_text(screen, "XLARGE: 14:35", 10, y, FontSize.XLARGE, amber)
        y += 110

        # ---- 颜色展示 ----
        colors_demo = [
            ("amber",  COLORS["amber"]),
            ("green",  COLORS["green"]),
            ("red",    COLORS["red"]),
            ("orange", COLORS["orange"]),
            ("white",  COLORS["white"]),
            ("dim",    COLORS["dim"]),
        ]
        x = 10
        for name, c in colors_demo:
            render_text(screen, name, x, y, FontSize.MEDIUM, c)
            w, _ = measure_text(name, FontSize.MEDIUM)
            x += w + 30

        # 帧率
        fps = clock.get_fps()
        render_text(screen, f"FPS:{fps:.0f}", WIDTH - 120, HEIGHT - 30,
                    FontSize.SMALL, dim)

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()

if __name__ == "__main__":
    main()
