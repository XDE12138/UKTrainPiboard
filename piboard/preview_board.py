"""
板面渲染预览脚本：展示完整 BoardContent 渲染效果（含跑马灯）。
运行：python3 preview_board.py
按 Q 退出。
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import pygame
from board.board_renderer import BoardRenderer
from providers.mock import MockProvider
from config import COLORS, PORTRAIT_WIDTH, PORTRAIT_HEIGHT, TICKER_SPEED

WIDTH, HEIGHT = PORTRAIT_WIDTH, PORTRAIT_HEIGHT

def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("PiBoard — Board Renderer Preview")
    clock = pygame.time.Clock()

    renderer = BoardRenderer(COLORS)

    # Overview first: the default desktop home page, followed by legacy demos.
    presets = [
        MockProvider(config={"preset": name}).fetch()
        for name in ("overview", "train", "weather", "calendar")
    ]
    current = 0

    ticker_offset = 0.0
    last_switch = pygame.time.get_ticks()
    SWITCH_INTERVAL = 5000  # 5秒切换一次

    running = True
    while running:
        dt = clock.tick(30) / 1000.0  # delta time in seconds

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    running = False
                if event.key == pygame.K_SPACE:
                    current = (current + 1) % len(presets)

        now = pygame.time.get_ticks()
        if now - last_switch > SWITCH_INTERVAL:
            current = (current + 1) % len(presets)
            last_switch = now

        content = presets[current]
        if content.ticker:
            ticker_offset += TICKER_SPEED * dt

        renderer.render(screen, content, int(ticker_offset))

        # FPS display
        from board.dot_font import render_text, FontSize
        fps = clock.get_fps()
        render_text(screen, f"FPS:{fps:.0f}  SPACE=next", 4, 4,
                    FontSize.SMALL, (40, 40, 40))

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()
