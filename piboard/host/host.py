"""
ScreenHost：顶层生命周期管理，替换原有 Renderer.run()。

职责：
- pygame 事件循环（quit / ESC）
- dirty flag 读写
- FPS_ACTIVE / FPS_IDLE 节流（保留现有低开销策略）
- 监听 app_state 变化（current_app / layout_id / slots / app_settings），通知 current_app
- 每帧驱动 current_app.render() 和 current_app.is_animating()
- 通过 Registry 校验已注册 App
- Host-level brightness dimming（Task 11）：app.render() 之后、flip() 之前叠加缓存 overlay

Task 7 更新：
- 全部改用 canonical state API（get_app_layout / get_app_slots / get_app_settings /
  get_device_settings），不再依赖 compat 属性。
- 移除 _APP_RELEVANT_SETTINGS 过滤器：app_settings 与 device_settings 现在是独立命名空间。

Task 8 更新：
- 移除 _CURRENT_APP_ID 硬编码。
- 构造器改为接收 app_instances dict（{app_id: BaseApp 实例}），由 main.py 预先装配。
- 主循环每帧检测 app_state.current_app 是否发生变化，变化时调用 _do_switch()。
- _do_switch() 实现完整的 on_deactivate → 切换 → on_state_changed（强制同步）→
  baseline 更新 → set_dirty → on_activate 生命周期，防止"state 新、实例旧"失真。

Task 11 更新：
- 新增 _sync_brightness() helper，从 device_settings 提取并应用亮度。
- 主循环 device_settings_changed 路径和 _do_switch() 都调用此 helper，
  保证切 app 后新 app 首帧即持有最新亮度。
- 使用缓存的 pygame.Surface overlay，只在 brightness 或 screen size 变化时重建。
- brightness=1.0 时走无 overlay 快速路径。
- brightness 变化不触发 on_state_changed()，不触发布局重建。

Settings 变化过滤说明：
- app_settings（color_theme / animations_enabled）变化 → 触发 on_state_changed()，重建 layout
- device_settings（brightness / orientation）变化 → 只更新 dirty flag，不重建 layout

orientation 说明：
- 本轮不从 state 读取 orientation 影响启动尺寸。
- TODO(future-task): 在设备设置 Task 中完成 orientation 与启动尺寸的绑定。
"""
import pygame
import logging
from state import app_state
from config import FPS_ACTIVE, FPS_IDLE
from host.registry import Registry
from apps.base import BaseApp

log = logging.getLogger(__name__)


class ScreenHost:

    def __init__(
        self,
        screen: pygame.Surface,
        registry: Registry,
        app_instances: dict,        # {app_id: BaseApp 实例}，由 main.py 预先装配
        logical_size=None,
        display_rotation: int = 0,
    ):
        self.screen = screen
        self._logical_size = logical_size or screen.get_size()
        self._display_rotation = display_rotation % 360
        self._render_target = self._build_render_target()
        self._registry = registry
        self._clock = pygame.time.Clock()
        self._running = False
        self._app_instances = app_instances  # {app_id: BaseApp}

        # 从 canonical state 确定初始 active app
        active_id = app_state.get_current_app()
        if active_id not in app_instances:
            log.warning(
                f"current_app='{active_id}' not in app_instances "
                f"{list(app_instances.keys())}; falling back to first registered"
            )
            active_id = next(iter(app_instances))
            app_state.set_current_app(active_id)  # 与 state 对齐

        self._active_app_id: str = active_id
        self._current_app: BaseApp = app_instances[active_id]

        # 记录上一帧状态（scoped to active app），用于检测变化
        self._last_layout_id: str = app_state.get_app_layout(active_id)
        self._last_slots: list = app_state.get_app_slots(active_id)
        self._last_app_settings: dict = dict(app_state.get_app_settings(active_id))
        self._last_device_settings: dict = dict(app_state.get_device_settings())

        # Brightness overlay（host-level dimming，所有 app 共享）
        # overlay 在 brightness 或 screen size 变化时重建，帧间零分配。
        # brightness=1.0 时 _brightness_overlay=None，走无 overlay 快速路径。
        self._current_brightness: float = self._last_device_settings.get("brightness", 1.0)
        self._brightness_overlay: "pygame.Surface | None" = None
        self._overlay_size: tuple = (0, 0)
        self._rebuild_brightness_overlay()

    def _build_render_target(self) -> pygame.Surface:
        if self._display_rotation == 0 and self._logical_size == self.screen.get_size():
            return self.screen
        return pygame.Surface(self._logical_size)

    def _present(self):
        if self._render_target is self.screen:
            return

        if self._display_rotation == 90:
            surf = pygame.transform.rotate(self._render_target, 90)
        elif self._display_rotation == 180:
            surf = pygame.transform.rotate(self._render_target, 180)
        elif self._display_rotation == 270:
            surf = pygame.transform.rotate(self._render_target, 270)
        else:
            surf = self._render_target

        self.screen.blit(surf, (0, 0))

    # ------------------------------------------------------------------
    # Brightness overlay helpers（Task 11）
    # ------------------------------------------------------------------

    def _rebuild_brightness_overlay(self):
        """重建 dimming overlay 缓存。
        brightness=1.0 → overlay=None（快速路径，不 blit）。
        其他值 → 黑色 SRCALPHA surface，alpha = (1-brightness)*255。
        仅在 brightness 或 screen size 变化时调用，帧间零分配。
        """
        b = self._current_brightness
        w, h = self._render_target.get_size()
        self._overlay_size = (w, h)
        if b >= 1.0:
            self._brightness_overlay = None
            return
        alpha = int((1.0 - b) * 255)
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((0, 0, 0, alpha))
        self._brightness_overlay = surf

    def _sync_brightness(self, device_settings: dict) -> bool:
        """从 device_settings 同步 brightness；有变化时重建 overlay。
        返回 True 表示发生了变化（调用方应将 dirty 置 True）。

        在两处调用以保证一致性：
          1. 主循环 device_settings_changed 路径
          2. _do_switch() 同步新 app baseline 时
        确保切 app 后新 app 首帧就已持有最新亮度。
        """
        new_b = device_settings.get("brightness", 1.0)
        if new_b == self._current_brightness:
            # 检查 screen size 是否变化（极少发生，但做完整性保护）
            if self._render_target.get_size() != self._overlay_size:
                self._rebuild_brightness_overlay()
            return False
        self._current_brightness = new_b
        self._rebuild_brightness_overlay()
        log.debug(f"Brightness updated: {new_b:.2f}")
        return True

    # ------------------------------------------------------------------
    # 主循环
    # ------------------------------------------------------------------

    def run(self):
        self._running = True
        app_state.set_dirty(True)
        self._current_app.on_activate()

        while self._running:
            # 处理事件
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    log.info("ScreenHost received pygame QUIT event")
                    self._running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        log.info("ScreenHost received ESC key")
                        self._running = False

            # --- App 切换检测（每帧一次 RLock dict lookup，开销可忽略）---
            requested_app = app_state.get_current_app()
            if requested_app != self._active_app_id:
                self._do_switch(requested_app)
                # _do_switch 已更新 baseline 并调用 on_state_changed + on_activate；
                # 本帧继续运行，baseline 与 state 一致，layout 检测不会重复触发。

            # 从 canonical state 读取当前值（以 active app 为准）
            dirty           = app_state.dirty
            layout_id       = app_state.get_app_layout(self._active_app_id)
            slots           = app_state.get_app_slots(self._active_app_id)
            app_settings    = app_state.get_app_settings(self._active_app_id)
            device_settings = app_state.get_device_settings()
            now_ms          = pygame.time.get_ticks()

            # 检测变化
            layout_changed       = (layout_id != self._last_layout_id
                                    or slots != self._last_slots)
            app_settings_changed = app_settings != self._last_app_settings
            device_settings_changed = device_settings != self._last_device_settings

            # layout 或 app_settings 变化 → 通知 App 重建
            if layout_changed or app_settings_changed:
                self._current_app.on_state_changed(layout_id, slots, app_settings)
                dirty = True

            # 更新 last 记录，防止下帧重复检测
            if layout_changed or app_settings_changed:
                self._last_layout_id    = layout_id
                self._last_slots        = list(slots)
                self._last_app_settings = dict(app_settings)
            if device_settings_changed:
                self._last_device_settings = dict(device_settings)
                # brightness 变化：同步 overlay，不触发 on_state_changed，不触发布局重建
                if self._sync_brightness(device_settings):
                    dirty = True  # 强制本帧渲染，overlay 立即生效

            next_render_ms = self._current_app.next_render_ms(now_ms)
            if next_render_ms is not None and now_ms >= next_render_ms:
                dirty = True

            # 渲染（保留原有 dirty flag + FPS 节流策略）
            if dirty or self._current_app.is_animating():
                dt = self._clock.get_time() / 1000.0
                self._current_app.render(self._render_target, dt)
                # Host-level brightness dimming：app.render() 之后、flip() 之前。
                # 所有 app（uk_station / system_status 等）统一经此路径，无需各自处理。
                if self._brightness_overlay is not None:
                    self._render_target.blit(self._brightness_overlay, (0, 0))
                self._present()
                pygame.display.flip()
                app_state.set_dirty(False)
                self._clock.tick(FPS_ACTIVE)
            else:
                self._clock.tick(FPS_IDLE)

        self._current_app.on_deactivate()
        pygame.quit()
        log.info("ScreenHost stopped")

    # ------------------------------------------------------------------
    # App 切换
    # ------------------------------------------------------------------

    def _do_switch(self, new_id: str):
        """
        完整 app 切换生命周期：
          1. on_deactivate() 旧 app
          2. 切换 _active_app_id / _current_app
          3. 强制 on_state_changed() 同步新 app 到当前 canonical state
             （防止非激活期间 layout/settings 被修改导致"state 新、实例旧"失真）
          4. 更新 baseline（本帧不再重复触发 on_state_changed）
          5. set_dirty(True) + on_activate() 新 app
        """
        if new_id not in self._app_instances:
            log.warning(f"_do_switch: '{new_id}' not in app_instances, ignoring")
            return

        log.info(f"App switch: {self._active_app_id} → {new_id}")

        # 1. 通知旧 app 即将离开
        self._current_app.on_deactivate()

        # 2. 切换 active 引用
        self._active_app_id = new_id
        self._current_app   = self._app_instances[new_id]

        # 3. 读取新 app 的当前 canonical state
        layout_id    = app_state.get_app_layout(new_id)
        slots        = app_state.get_app_slots(new_id)
        app_settings = app_state.get_app_settings(new_id)
        dev_settings = app_state.get_device_settings()

        # 4. 强制同步（无论非激活期间是否有变化，保证实例与 state 一致）
        self._current_app.on_state_changed(layout_id, slots, app_settings)

        # 5. 更新 baseline（本帧主循环读到的值与 baseline 相同 → 不会重复触发）
        self._last_layout_id       = layout_id
        self._last_slots           = list(slots)
        self._last_app_settings    = dict(app_settings)
        self._last_device_settings = dict(dev_settings)
        # 同步 brightness overlay：保证新 app 首帧即持有最新亮度，
        # 防止 brightness + app switch 在同一帧内导致主循环看不到 delta。
        self._sync_brightness(dev_settings)

        # 6. 激活新 app
        app_state.set_dirty(True)
        self._current_app.on_activate()

    # ------------------------------------------------------------------

    def stop(self):
        self._running = False
