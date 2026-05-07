"""
PiBoard 入口：启动 pygame 主循环 + Flask 子线程。

启动参数：
  --window          窗口模式（开发机调试）
  --mock            兼容保留参数（当前不改变 Provider 行为）
  --provider <id>   启动后显示的 Provider（默认 mock）
  --layout <id>     启动布局（single/dual/carousel，默认 single）
  --portrait        竖屏模式（600×1024，可被 --width/--height 覆盖）
  --display-rotate  物理输出旋转（kmsdrm 下替代 Wayland transform）
"""
import argparse
import logging
import os
import sys
import threading

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("piboard")


def parse_args():
    p = argparse.ArgumentParser(description="PiBoard Display System")
    p.add_argument("--window",   action="store_true",
                   help="窗口模式（不需要 Pi）")
    p.add_argument("--mock",     action="store_true",
                   help="兼容保留参数；当前不改变 Provider 行为")
    p.add_argument("--provider", default=None,
                   help="启动后显示的 Provider ID")
    p.add_argument("--layout",   default=None,
                   choices=["single", "dual", "carousel"],
                   help="启动布局（仅在显式传入时覆盖已持久化状态）")
    p.add_argument("--portrait", action="store_true",
                   help="竖屏模式（默认 600×1024）")
    p.add_argument("--width",    type=int, default=None)
    p.add_argument("--height",   type=int, default=None)
    p.add_argument("--display-rotate", type=int, default=0,
                   choices=[0, 90, 180, 270],
                   help="物理显示旋转角度；kmsdrm 下用于横屏 HDMI 面板竖装")
    return p.parse_args()


def setup_pygame(args, saved_orientation: str = "landscape"):
    """初始化 pygame 窗口。

    启动尺寸 precedence（高 → 低）：
      1. --width AND --height 同时传入 → 直接使用
      2. --portrait flag            → PORTRAIT_WIDTH × PORTRAIT_HEIGHT 作默认
      3. 持久化 device_settings.orientation == "portrait" → 同上
      4. 否则                       → SCREEN_WIDTH × SCREEN_HEIGHT (landscape)

    --portrait / --width / --height 只影响本次启动，不写回 device_settings。
    """
    import pygame
    from config import SCREEN_WIDTH, SCREEN_HEIGHT, PORTRAIT_WIDTH, PORTRAIT_HEIGHT

    if not args.window:
        os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    pygame.init()

    if args.portrait or saved_orientation == "portrait":
        default_w, default_h = PORTRAIT_WIDTH, PORTRAIT_HEIGHT
    else:
        default_w, default_h = SCREEN_WIDTH, SCREEN_HEIGHT

    w = args.width  or default_w
    h = args.height or default_h

    rotate = args.display_rotate
    physical_w, physical_h = (h, w) if rotate in (90, 270) else (w, h)

    flags = 0 if args.window else pygame.FULLSCREEN
    screen = pygame.display.set_mode((physical_w, physical_h), flags)
    pygame.display.set_caption("PiBoard")
    pygame.mouse.set_visible(False)

    orientation = "portrait" if h > w else "landscape"
    if rotate:
        log.info(
            f"Screen: logical {w}×{h} ({orientation}), "
            f"physical {physical_w}×{physical_h}, rotate={rotate}"
        )
    else:
        log.info(f"Screen: {w}×{h} ({orientation})")
    return screen, (w, h), rotate


def build_providers():
    """实例化所有 Provider 并应用初始配置。"""
    from state import app_state
    from providers.mock import MockProvider
    from providers.train_bridge import TrainSourceBridge as TrainProvider
    from providers.weather_bridge import WeatherSourceBridge as WeatherProvider
    from providers.calendar_bridge import CalendarSourceBridge as CalendarProvider
    from providers.custom import CustomProvider

    providers = {}
    for cls in [WeatherProvider, CalendarProvider, TrainProvider,
                CustomProvider, MockProvider]:
        cfg = app_state.get_source_config(cls.provider_id)
        p = cls(config=cfg)
        providers[p.provider_id] = p

    if "mock" in providers and "weather" in providers:
        providers["mock"].set_linked_weather_provider(providers["weather"])
    if "mock" in providers and "calendar" in providers:
        providers["mock"].set_linked_calendar_provider(providers["calendar"])
    if "mock" in providers and "train" in providers:
        providers["mock"].set_linked_train_provider(providers["train"])

    return providers



def start_web_server(providers, fetcher):
    """在 daemon 线程中启动 Flask。"""
    from web.server import create_app
    from config import WEB_HOST, WEB_PORT
    app = create_app(providers, fetcher)
    # 单线程 Flask，避免 SDL 和多线程冲突
    app.run(host=WEB_HOST, port=WEB_PORT,
            threaded=False, use_reloader=False)


def main():
    args = parse_args()

    # 加载持久化状态（自动处理 v0 → v1 迁移）
    from state import app_state
    from config import STATE_FILE
    app_state.load(STATE_FILE)
    # 绑定自动持久化路径：此后 canonical setter 修改即时落盘
    app_state.set_save_path(STATE_FILE)

    # CLI 覆盖：仅在用户显式传入 --provider 或 --layout 时才调用 set_app_layout。
    # load() 之后默认保留已持久化的 layout/slots，不做隐式重置。
    # --provider 或 --layout 任意一个被显式传入，视为完整覆盖意图。
    cli_override = args.provider is not None or args.layout is not None
    if cli_override:
        layout = args.layout or "single"
        if args.provider:
            slots = [args.provider]
        else:
            slots = ["mock"]
            if layout == "dual":
                slots = ["mock", "mock"]
            elif layout == "carousel":
                slots = ["mock"]
        app_state.set_app_layout("uk_station", layout, slots)
    # else: 保留 load() 恢复的持久化 layout/slots，不覆盖

    # 构建 Provider（使用 canonical source_config 读取）
    providers = build_providers()

    # 装配 App：在 fetcher 启动和 pygame 初始化之前完成，
    # 确保 catalog / assembly 不一致时 fail fast 且不泄漏已启动资源。
    from host.registry import registry
    from host.host import ScreenHost
    from apps.assembly import assemble_apps

    app_instances = assemble_apps(registry, providers, app_state)

    # 后台数据拉取
    from data.fetcher import DataFetcher
    fetcher = DataFetcher()
    for p in providers.values():
        fetcher.register(p)
    fetcher.start()

    # 初始化 pygame（读取持久化方向作为默认尺寸依据）
    saved_orientation = app_state.get_device_settings().get("orientation", "landscape")
    screen, logical_size, display_rotation = setup_pygame(args, saved_orientation)

    host = ScreenHost(
        screen=screen,
        registry=registry,
        app_instances=app_instances,
        logical_size=logical_size,
        display_rotation=display_rotation,
    )

    # 启动 Flask（daemon 线程）
    web_thread = threading.Thread(
        target=start_web_server,
        args=(providers, fetcher),
        daemon=True,
        name="FlaskServer",
    )
    web_thread.start()
    from config import WEB_PORT
    log.info(f"Web server starting on port {WEB_PORT}")

    log.info("PiBoard started. Press ESC to quit.")
    try:
        host.run()
    finally:
        fetcher.stop()
        app_state.save(STATE_FILE)
        log.info("PiBoard exited.")


if __name__ == "__main__":
    main()
