"""
Flask + flask-sock Web 控制台服务器。
单线程模式，与 pygame 主线程通过 state.py 通信。

Task 7: 迁移到 app/source/device-centric 控制语义。

Contract:
  出站（/api/state、WS 广播）: 仅使用 canonical 格式。
  入站（旧 POST 路由、旧 WS action）: 保留 compat 接受，内部委托到 canonical 写入方法。

已知 app ID:
  _KNOWN_APPS — 用于 /api/app/<app_id>/... 路由的合法性校验。
"""
import json
import logging
import os
import socket
import subprocess
import threading
import time
from concurrent.futures import TimeoutError
from typing import Dict

from flask import Flask, jsonify, request, render_template
from flask_sock import Sock

from state import app_state
from providers.base import BaseProvider
from data.fetcher import DataFetcher
from apps.catalog import APP_CATALOG, KNOWN_APP_IDS, DEFAULT_APP_ID

log = logging.getLogger(__name__)

# WebSocket 连接池（用于服务端推送）
_ws_clients: set = set()
_ws_lock = threading.Lock()

# 当前支持的 app ID 集合（从 catalog 派生，勿手工维护）
_KNOWN_APPS = KNOWN_APP_IDS

# compat: /api/settings 入站时，按键名分流到 app_settings 或 device_settings
_APP_SETTINGS_KEYS  = frozenset({"color_theme", "animations_enabled"})
_DEVICE_SETTINGS_KEYS = frozenset({"brightness", "orientation"})


def create_app(providers: Dict[str, BaseProvider],
               fetcher: DataFetcher) -> Flask:
    app = Flask(__name__,
                template_folder="templates",
                static_folder="static")
    app.config["SOCK_SERVER_OPTIONS"] = {"ping_interval": 25}
    sock = Sock(app)

    # ------------------------------------------------------------------
    # 辅助：构建 sources 响应体（/api/sources 和 /api/providers 共用）
    # ------------------------------------------------------------------

    def _build_sources_response() -> dict:
        result = {}
        for pid, p in providers.items():
            result[pid] = {
                "source_id":     p.provider_id,
                "display_name":  p.display_name,
                "refresh_interval": p.get_refresh_interval(),
                "schema":        p.get_config_schema(),
                "config":        app_state.get_source_config(pid),
            }
        return result

    # ------------------------------------------------------------------
    # REST API — Canonical
    # ------------------------------------------------------------------

    @app.route("/")
    def index():
        return render_template(
            "index.html",
            app_catalog=APP_CATALOG,
            default_app_id=DEFAULT_APP_ID,
        )

    @app.route("/api/state")
    def api_state():
        """返回完整 canonical v1 状态（唯一出站格式）。"""
        return jsonify(app_state.get_all())

    @app.route("/api/sources")
    def api_sources():
        return jsonify(_build_sources_response())

    @app.route("/api/device-status")
    def api_device_status():
        return jsonify(_build_device_status())

    @app.route("/api/app/<app_id>/layout", methods=["POST"])
    def api_app_layout(app_id):
        if app_id not in _KNOWN_APPS:
            return jsonify({"error": "unknown app"}), 400
        data   = request.get_json(force=True)
        layout = data.get("layout", "single")
        slots  = data.get("slots", ["mock"])
        app_state.set_app_layout(app_id, layout, slots)
        _broadcast({"type": "app_layout_changed",
                    "app_id": app_id, "layout": layout, "slots": slots})
        return jsonify({"ok": True})

    @app.route("/api/source/<source_id>/config", methods=["POST"])
    def api_source_config(source_id):
        if source_id not in providers:
            return jsonify({"error": "unknown source"}), 404
        data = request.get_json(force=True)
        app_state.update_source_config(source_id, data)
        providers[source_id].update_config(data)
        future = fetcher.force_refresh(source_id)
        wait_result = _wait_for_refresh(source_id, future)
        if wait_result is not None:
            return wait_result
        _broadcast({"type": "source_config_changed", "source_id": source_id})
        return jsonify({"ok": True})

    @app.route("/api/source/<source_id>/refresh", methods=["POST"])
    def api_source_refresh(source_id):
        if source_id not in providers:
            return jsonify({"error": "unknown source"}), 404
        future = fetcher.force_refresh(source_id)
        wait_result = _wait_for_refresh(source_id, future)
        if wait_result is not None:
            return wait_result
        return jsonify({"ok": True})

    @app.route("/api/device-settings", methods=["POST"])
    def api_device_settings():
        data = request.get_json(force=True)
        app_state.update_device_settings(data)
        _broadcast({"type": "device_settings_changed",
                    "device_settings": app_state.get_device_settings()})
        return jsonify({"ok": True})

    @app.route("/api/app/<app_id>/settings", methods=["POST"])
    def api_app_settings(app_id):
        if app_id not in _KNOWN_APPS:
            return jsonify({"error": "unknown app"}), 400
        data = request.get_json(force=True)
        app_state.update_app_settings(app_id, data)
        _broadcast({"type": "app_settings_changed",
                    "app_id": app_id,
                    "app_settings": app_state.get_app_settings(app_id)})
        return jsonify({"ok": True})

    @app.route("/api/current-app", methods=["POST"])
    def api_current_app():
        """切换当前 active app（Task 8）。"""
        data   = request.get_json(force=True)
        app_id = data.get("app_id", "")
        if app_id not in _KNOWN_APPS:
            return jsonify({"error": "unknown app"}), 400
        ok = app_state.set_current_app(app_id)
        if not ok:
            return jsonify({"error": "switch rejected"}), 400
        _broadcast({"type": "current_app_changed", "current_app": app_id})
        return jsonify({"ok": True, "current_app": app_id})

    # ------------------------------------------------------------------
    # REST API — Inbound compat（旧路由，内部委托到 canonical 写入）
    # ------------------------------------------------------------------

    @app.route("/api/providers")
    def api_providers():
        """COMPAT: /api/providers → /api/sources 相同响应体。"""
        return jsonify(_build_sources_response())

    @app.route("/api/layout", methods=["POST"])
    def api_layout():
        """COMPAT: POST /api/layout → set_app_layout("uk_station", ...)"""
        data   = request.get_json(force=True)
        layout = data.get("layout", "single")
        slots  = data.get("slots", ["mock"])
        app_state.set_app_layout("uk_station", layout, slots)
        _broadcast({"type": "app_layout_changed",
                    "app_id": "uk_station", "layout": layout, "slots": slots})
        return jsonify({"ok": True})

    @app.route("/api/provider/<pid>/config", methods=["POST"])
    def api_provider_config(pid):
        """COMPAT: POST /api/provider/<pid>/config → update_source_config()"""
        if pid not in providers:
            return jsonify({"error": "unknown provider"}), 404
        data = request.get_json(force=True)
        app_state.update_source_config(pid, data)
        providers[pid].update_config(data)
        future = fetcher.force_refresh(pid)
        wait_result = _wait_for_refresh(pid, future)
        if wait_result is not None:
            return wait_result
        _broadcast({"type": "source_config_changed", "source_id": pid})
        return jsonify({"ok": True})

    @app.route("/api/provider/<pid>/refresh", methods=["POST"])
    def api_provider_refresh(pid):
        """COMPAT: POST /api/provider/<pid>/refresh → fetcher.force_refresh()"""
        if pid not in providers:
            return jsonify({"error": "unknown provider"}), 404
        future = fetcher.force_refresh(pid)
        wait_result = _wait_for_refresh(pid, future)
        if wait_result is not None:
            return wait_result
        return jsonify({"ok": True})

    @app.route("/api/settings", methods=["POST"])
    def api_settings():
        """COMPAT: POST /api/settings → 按键名分流到 device/app settings。"""
        data = request.get_json(force=True)
        app_part    = {k: v for k, v in data.items() if k in _APP_SETTINGS_KEYS}
        device_part = {k: v for k, v in data.items() if k in _DEVICE_SETTINGS_KEYS}
        if app_part:
            app_state.update_app_settings("uk_station", app_part)
            _broadcast({"type": "app_settings_changed",
                        "app_id": "uk_station",
                        "app_settings": app_state.get_app_settings("uk_station")})
        if device_part:
            app_state.update_device_settings(device_part)
            _broadcast({"type": "device_settings_changed",
                        "device_settings": app_state.get_device_settings()})
        return jsonify({"ok": True})

    @app.route("/api/orientation", methods=["POST"])
    def api_orientation():
        """COMPAT: POST /api/orientation → update_device_settings()"""
        data = request.get_json(force=True)
        orientation = data.get("orientation", "landscape")
        if orientation not in ("landscape", "portrait"):
            return jsonify({"error": "invalid orientation"}), 400
        app_state.update_device_settings({"orientation": orientation})
        _broadcast({"type": "device_settings_changed",
                    "device_settings": app_state.get_device_settings()})
        # pygame 窗口尺寸无法运行时动态修改，需重启生效
        return jsonify({"ok": True, "restart_required": True})

    # ------------------------------------------------------------------
    # WebSocket
    # ------------------------------------------------------------------

    @sock.route("/ws")
    def ws_handler(ws):
        with _ws_lock:
            _ws_clients.add(ws)
        try:
            # 初始推送完整 canonical 状态
            _send_ws(ws, {"type": "state", "data": app_state.get_all()})
            while True:
                msg = ws.receive(timeout=30)
                if msg is None:
                    break
                try:
                    data = json.loads(msg)
                    _handle_ws_message(data, providers, fetcher, ws)
                except Exception as e:
                    log.warning(f"WS message error: {e}")
        except Exception:
            pass
        finally:
            with _ws_lock:
                _ws_clients.discard(ws)

    return app


def _wait_for_refresh(source_id: str, future):
    """Optionally wait for a forced refresh before returning to the Web UI."""
    if request.args.get("wait") != "1":
        return None
    if future is None:
        return jsonify({"error": "unknown source"}), 404
    try:
        ok = future.result(timeout=15)
    except TimeoutError:
        return jsonify({"error": f"{source_id} 刷新超时，请稍后重试。"}), 504
    if not ok:
        return jsonify({"error": f"{source_id} 刷新失败，请检查配置或网络。"}), 502
    return None


# ------------------------------------------------------------------
# WS helpers
# ------------------------------------------------------------------

def _handle_ws_message(data: dict, providers, fetcher, ws):
    action = data.get("action")

    # --- Canonical actions ---
    if action == "set_app_layout":
        app_id = data.get("app_id", "uk_station")
        if app_id not in _KNOWN_APPS:
            log.warning(f"WS set_app_layout: unknown app_id '{app_id}', ignored")
            return
        app_state.set_app_layout(app_id, data["layout"], data["slots"])
        _broadcast({"type": "app_layout_changed",
                    "app_id": app_id,
                    "layout": data["layout"],
                    "slots": data["slots"]})

    elif action == "update_source_config":
        sid = data.get("source_id", "")
        if sid in providers:
            app_state.update_source_config(sid, data["config"])
            providers[sid].update_config(data["config"])
            fetcher.force_refresh(sid)
            _broadcast({"type": "source_config_changed", "source_id": sid})

    elif action == "update_device_settings":
        app_state.update_device_settings(data.get("device_settings", {}))
        _broadcast({"type": "device_settings_changed",
                    "device_settings": app_state.get_device_settings()})

    elif action == "update_app_settings":
        app_id = data.get("app_id", "uk_station")
        if app_id not in _KNOWN_APPS:
            log.warning(f"WS update_app_settings: unknown app_id '{app_id}', ignored")
            return
        app_state.update_app_settings(app_id, data.get("app_settings", {}))
        _broadcast({"type": "app_settings_changed",
                    "app_id": app_id,
                    "app_settings": app_state.get_app_settings(app_id)})

    elif action == "switch_app":
        # Task 8: 切换 current_app
        app_id = data.get("app_id", "")
        if app_id not in _KNOWN_APPS:
            log.warning(f"WS switch_app: unknown app_id '{app_id}', ignored")
            return
        ok = app_state.set_current_app(app_id)
        if ok:
            _broadcast({"type": "current_app_changed", "current_app": app_id})

    # --- Inbound compat actions ---
    elif action == "set_layout":
        app_state.set_app_layout("uk_station", data["layout"], data["slots"])
        _broadcast({"type": "app_layout_changed",
                    "app_id": "uk_station",
                    "layout": data["layout"],
                    "slots": data["slots"]})

    elif action == "update_config":
        pid = data.get("provider_id", "")
        if pid in providers:
            app_state.update_source_config(pid, data["config"])
            providers[pid].update_config(data["config"])
            fetcher.force_refresh(pid)
            _broadcast({"type": "source_config_changed", "source_id": pid})

    elif action == "update_settings":
        settings = data.get("settings", {})
        app_part    = {k: v for k, v in settings.items() if k in _APP_SETTINGS_KEYS}
        device_part = {k: v for k, v in settings.items() if k in _DEVICE_SETTINGS_KEYS}
        if app_part:
            app_state.update_app_settings("uk_station", app_part)
            _broadcast({"type": "app_settings_changed",
                        "app_id": "uk_station",
                        "app_settings": app_state.get_app_settings("uk_station")})
        if device_part:
            app_state.update_device_settings(device_part)
            _broadcast({"type": "device_settings_changed",
                        "device_settings": app_state.get_device_settings()})

    elif action == "refresh":
        fetcher.force_refresh(data.get("provider_id", ""))

    elif action == "get_state":
        _send_ws(ws, {"type": "state", "data": app_state.get_all()})


def _send_ws(ws, data: dict):
    try:
        ws.send(json.dumps(data))
    except Exception:
        pass


def _broadcast(data: dict):
    """向所有连接的 WS 客户端推送 canonical 消息。"""
    with _ws_lock:
        clients = set(_ws_clients)
    for ws in clients:
        _send_ws(ws, data)


def _build_device_status() -> dict:
    """返回 Web 控制台用的轻量设备状态。Mac 本地无法读取的 Pi 字段为 None。"""
    state = app_state.get_all()
    return {
        "ok": True,
        "hostname": socket.gethostname(),
        "time": int(time.time()),
        "is_pi": _is_raspberry_pi(),
        "temp_c": _read_temperature_c(),
        "throttled": _read_throttled(),
        "current_app": state.get("current_app"),
        "apps": state.get("apps", {}),
        "device_settings": state.get("device_settings", {}),
    }


def _is_raspberry_pi() -> bool:
    model_path = "/sys/firmware/devicetree/base/model"
    try:
        if os.path.exists(model_path):
            with open(model_path, "r", encoding="utf-8", errors="ignore") as f:
                return "raspberry pi" in f.read().lower()
    except OSError:
        pass
    return False


def _read_temperature_c():
    temp_path = "/sys/class/thermal/thermal_zone0/temp"
    try:
        with open(temp_path, "r", encoding="utf-8") as f:
            return round(int(f.read().strip()) / 1000.0, 1)
    except (OSError, ValueError):
        return None


def _read_throttled():
    try:
        result = subprocess.run(
            ["vcgencmd", "get_throttled"],
            check=False,
            capture_output=True,
            text=True,
            timeout=1,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    text = result.stdout.strip()
    if not text:
        return None
    return text.split("=", 1)[-1] if "=" in text else text
