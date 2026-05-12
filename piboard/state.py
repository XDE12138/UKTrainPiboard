"""
全局共享状态（单例，线程安全）。
pygame 主线程和 Flask 线程通过此模块读写状态。

Task 7: 迁移到 canonical state model（schema_version=1）。
Task 8: 支持多 App runtime 切换。移除单 App 钳位，新增 set_current_app()。
Task 10: 持久化收口。串行化 + 原子替换写盘；canonical setter 自动落盘；
         device_settings key 白名单 + orientation 合法值校验。

Canonical 结构：
  schema_version: int
  current_app: str
  apps:
    <app_id>:
      layout: str
      slots: List[str]
      app_settings: dict          # 触发 layout 重建的键（color_theme, animations_enabled）
  source_configs: dict            # 原 providers_config，键为 source/provider id
  device_settings: dict           # 设备级设置（brightness, orientation）

Legacy compat 接口（标注 # COMPAT）：
  仅供 web/server.py 的旧 POST 路由使用，任何 Task 7 新调用点不应依赖这些接口。
"""
import threading
import json
import os
import copy
import logging
from typing import Dict, Any, List

from apps.catalog import APP_CATALOG, KNOWN_APP_IDS, DEFAULT_APP_ID

log = logging.getLogger(__name__)

# app_settings 中包含的键（触发 layout 重建）；其余 settings 键归 device_settings
_APP_SETTINGS_KEYS = frozenset({"color_theme", "animations_enabled"})
# device_settings 中包含的键
_DEVICE_SETTINGS_KEYS = frozenset({"brightness", "orientation"})
_DEFAULT_WEATHER_CONFIG = {
    "location_mode": "auto",
    "city": "",
    "latitude": "",
    "longitude": "",
    "api_key": "",
    "units": "metric",
}

def _default_state() -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "current_app": DEFAULT_APP_ID,
        "apps": {
            spec.app_id: {
                "layout": spec.default_layout,
                "slots":  list(spec.default_slots),
                "app_settings": dict(spec.default_app_settings),
            }
            for spec in APP_CATALOG
        },
        "source_configs": {
            "mock":     {},
            "train":    {"station_crs": "KGX", "destination_crs": "",
                         "api_key": "", "data_source": "mock",
                         "huxley2_base_url":
                         "https://national-rail-api.davwheat.dev"},
            "weather":  dict(_DEFAULT_WEATHER_CONFIG),
            "calendar": {"ical_url": "", "lookahead_days": 3},
            "custom":   {
                "header_left": "", "header_right": "",
                "title": "PiBoard", "subtitle": "Custom Display",
                "rows": [], "footer": "", "status_text": "OK",
                "status_color": "green", "ticker": "",
            },
        },
        "device_settings": {
            "brightness": 1.0,
            "orientation": "landscape",
        },
        "dirty": True,
    }


def _migrate_v0_to_v1(saved: Dict[str, Any]) -> Dict[str, Any]:
    """将旧格式（无 schema_version）迁移到 v1 canonical 结构。"""
    new = _default_state()

    # Layout / slots
    if "current_layout" in saved:
        new["apps"]["uk_station"]["layout"] = saved["current_layout"]
    if "layout_slots" in saved:
        new["apps"]["uk_station"]["slots"] = list(saved["layout_slots"])

    # Source configs（原 providers_config）
    if "providers_config" in saved:
        # 深合并：保留已有默认值，用 saved 值覆盖
        for sid, cfg in saved["providers_config"].items():
            if sid in new["source_configs"]:
                new["source_configs"][sid].update(cfg)
            else:
                new["source_configs"][sid] = dict(cfg)

    # Settings split
    old_settings = saved.get("settings", {})
    for key in _APP_SETTINGS_KEYS:
        if key in old_settings:
            new["apps"]["uk_station"]["app_settings"][key] = old_settings[key]
    for key in _DEVICE_SETTINGS_KEYS:
        if key in old_settings:
            new["device_settings"][key] = old_settings[key]

    return new


def _normalize_source_configs(source_configs: Dict[str, Any]):
    """Fill newer source config keys and retire legacy London weather defaults."""
    weather_before_merge = source_configs.get("weather", {})
    weather_was_legacy_london_default = (
        isinstance(weather_before_merge, dict)
        and "location_mode" not in weather_before_merge
        and set(weather_before_merge.keys()) <= {"city", "api_key", "units"}
        and weather_before_merge.get("city") == "London"
        and not weather_before_merge.get("api_key")
    )

    defaults = _default_state()["source_configs"]
    for sid, default_cfg in defaults.items():
        current = source_configs.get(sid)
        if not isinstance(current, dict):
            source_configs[sid] = copy.deepcopy(default_cfg)
            continue
        merged = copy.deepcopy(default_cfg)
        merged.update(current)
        source_configs[sid] = merged

    weather = source_configs.get("weather", {})
    if "location_mode" not in weather:
        weather["location_mode"] = "manual" if weather.get("city") else "auto"
    if weather_was_legacy_london_default:
        weather["location_mode"] = "auto"
        weather["city"] = ""
    for key, value in _DEFAULT_WEATHER_CONFIG.items():
        weather.setdefault(key, value)
    source_configs["weather"] = weather


class AppState:
    """线程安全的全局状态单例（canonical v1 model）。"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._rlock = threading.RLock()
        self._persist_lock = threading.Lock()   # 串行化写盘，独立于 _rlock
        self._save_path: str = ""               # 绑定后 canonical setter 自动落盘
        self._state: Dict[str, Any] = _default_state()

    # ------------------------------------------------------------------
    # Canonical 读取
    # ------------------------------------------------------------------

    def get_current_app(self) -> str:
        with self._rlock:
            return self._state["current_app"]

    def get_app_state(self, app_id: str) -> Dict[str, Any]:
        """返回 apps[app_id] 的深拷贝。app_id 不存在时返回空 dict。"""
        with self._rlock:
            return copy.deepcopy(self._state["apps"].get(app_id, {}))

    def get_app_layout(self, app_id: str) -> str:
        with self._rlock:
            return self._state["apps"].get(app_id, {}).get("layout", "single")

    def get_app_slots(self, app_id: str) -> List[str]:
        with self._rlock:
            return list(self._state["apps"].get(app_id, {}).get("slots", ["mock"]))

    def get_app_settings(self, app_id: str) -> Dict[str, Any]:
        with self._rlock:
            return dict(self._state["apps"].get(app_id, {}).get("app_settings", {}))

    def get_source_config(self, source_id: str) -> Dict[str, Any]:
        with self._rlock:
            return dict(self._state["source_configs"].get(source_id, {}))

    def get_all_source_configs(self) -> Dict[str, Any]:
        with self._rlock:
            return copy.deepcopy(self._state["source_configs"])

    def get_device_settings(self) -> Dict[str, Any]:
        with self._rlock:
            return dict(self._state["device_settings"])

    @property
    def dirty(self) -> bool:
        with self._rlock:
            return self._state["dirty"]

    def get_all(self) -> Dict[str, Any]:
        """返回完整 canonical 状态快照（深拷贝）。"""
        with self._rlock:
            return copy.deepcopy(self._state)

    # ------------------------------------------------------------------
    # Canonical 写入
    # ------------------------------------------------------------------

    def set_dirty(self, value: bool = True):
        with self._rlock:
            self._state["dirty"] = value

    def set_app_layout(self, app_id: str, layout_id: str, slots: List[str]):
        with self._rlock:
            if app_id not in self._state["apps"]:
                log.warning(f"set_app_layout: unknown app_id '{app_id}', ignored")
                return
            self._state["apps"][app_id]["layout"] = layout_id
            self._state["apps"][app_id]["slots"] = list(slots)
            self._state["dirty"] = True
        log.info(f"App layout changed: app={app_id}, layout={layout_id}, slots={slots}")
        self._persist()

    def update_source_config(self, source_id: str, config: Dict[str, Any]):
        with self._rlock:
            if source_id not in self._state["source_configs"]:
                self._state["source_configs"][source_id] = {}
            self._state["source_configs"][source_id].update(config)
            self._state["dirty"] = True
        log.info(f"Source config updated: {source_id}")
        self._persist()

    @staticmethod
    def _sanitize_device_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
        """过滤 device_settings：只保留白名单键，各键有专属合法性规则。
        运行时写入路径（update_device_settings）和启动恢复路径（load）共用此规则。

        brightness contract [0.1, 1.0]：
          - 超出范围的数值 clamp（不拒绝，给前端 slider 容错）
          - 非数值类型 → warn + ignore
        orientation contract {"landscape", "portrait"}：
          - 非法字符串 → warn + ignore
        """
        filtered: Dict[str, Any] = {}
        for k, v in settings.items():
            if k not in _DEVICE_SETTINGS_KEYS:
                log.warning(f"device_settings: unknown key '{k}', ignored")
                continue
            if k == "brightness":
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    log.warning(f"device_settings: non-numeric brightness='{v}', ignored")
                    continue
                v = max(0.1, min(1.0, v))
            if k == "orientation" and v not in ("landscape", "portrait"):
                log.warning(f"device_settings: invalid orientation='{v}', ignored")
                continue
            filtered[k] = v
        return filtered

    def update_device_settings(self, settings: Dict[str, Any]):
        filtered = self._sanitize_device_settings(settings)
        if not filtered:
            return
        with self._rlock:
            self._state["device_settings"].update(filtered)
            self._state["dirty"] = True
        log.info(f"Device settings updated: {filtered}")
        self._persist()

    def update_app_settings(self, app_id: str, settings: Dict[str, Any]):
        with self._rlock:
            if app_id not in self._state["apps"]:
                log.warning(f"update_app_settings: unknown app_id '{app_id}', ignored")
                return
            self._state["apps"][app_id]["app_settings"].update(settings)
            self._state["dirty"] = True
        log.info(f"App settings updated: app={app_id}, settings={settings}")
        self._persist()

    def set_current_app(self, app_id: str) -> bool:
        """切换当前 active app。app_id 必须在 apps 字典中；否则拒绝并返回 False。"""
        with self._rlock:
            if app_id not in self._state["apps"]:
                log.warning(f"set_current_app: unknown app_id '{app_id}', rejected")
                return False
            self._state["current_app"] = app_id
            self._state["dirty"] = True
        log.info(f"Current app switched to: {app_id}")
        self._persist()
        return True

    # ------------------------------------------------------------------
    # COMPAT — 旧接口，仅供 server.py 旧路由使用，Task 7 新代码不应调用
    # ------------------------------------------------------------------

    @property
    def current_layout(self) -> str:  # COMPAT
        return self.get_app_layout("uk_station")

    @property
    def layout_slots(self) -> List[str]:  # COMPAT
        return self.get_app_slots("uk_station")

    @property
    def settings(self) -> Dict[str, Any]:  # COMPAT
        """合并视图：device_settings + 当前 app 的 app_settings。"""
        with self._rlock:
            merged = dict(self._state["device_settings"])
            merged.update(self._state["apps"]["uk_station"]["app_settings"])
            return merged

    def get_provider_config(self, provider_id: str) -> Dict[str, Any]:  # COMPAT
        return self.get_source_config(provider_id)

    def set_layout(self, layout_id: str, slots: List[str]):  # COMPAT
        self.set_app_layout("uk_station", layout_id, slots)

    def update_provider_config(self, provider_id: str, config: Dict[str, Any]):  # COMPAT
        self.update_source_config(provider_id, config)

    def update_settings(self, settings: Dict[str, Any]):  # COMPAT
        """将旧格式 settings 按键分流到 device_settings 或 app_settings。"""
        app_part = {k: v for k, v in settings.items() if k in _APP_SETTINGS_KEYS}
        device_part = {k: v for k, v in settings.items() if k in _DEVICE_SETTINGS_KEYS}
        if app_part:
            self.update_app_settings("uk_station", app_part)
        if device_part:
            self.update_device_settings(device_part)

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------

    def set_save_path(self, path: str):
        """绑定自动持久化路径（main 启动时在 load 后调用一次）。"""
        with self._rlock:
            self._save_path = path

    def _persist(self):
        """如已绑定路径，立即落盘。由 canonical setter 在 _rlock 外调用。"""
        if self._save_path:
            self.save(self._save_path)

    def save(self, path: str):
        """保存 canonical 状态到 JSON 文件（串行化 + durability + 原子替换）。

        写入顺序：
          1. json.dump → tmp 文件
          2. flush() 把用户态缓冲推到 OS
          3. fsync(tmp)  确保 tmp 数据落到存储介质
          4. os.replace(tmp, path)  原子替换（POSIX）
          5. fsync(parent dir)  把 rename 的目录项也同步，防止断电后目录看不到新文件
        """
        with self._persist_lock:
            try:
                data = self.get_all()
                # 不持久化 dirty 标志
                data.pop("dirty", None)
                dir_path = os.path.dirname(path)
                tmp_path = path + ".tmp"
                os.makedirs(dir_path, exist_ok=True)
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.flush()               # 用户态缓冲 → OS 页缓存
                    os.fsync(f.fileno())    # OS 页缓存 → 存储介质
                os.replace(tmp_path, path)  # POSIX 原子 rename
                # 父目录 fsync：把 rename 产生的目录项变更也落盘
                dir_fd = os.open(dir_path, os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except Exception as e:
                log.error(f"State save failed: {e}")

    def load(self, path: str):
        """从 JSON 文件恢复状态；自动处理 v0 → v1 迁移。"""
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                saved = json.load(f)

            version = saved.get("schema_version")
            if version is None:
                log.info("State file is v0 format, migrating to v1...")
                migrated = _migrate_v0_to_v1(saved)
            elif version == 1:
                migrated = saved
            else:
                log.warning(f"Unknown schema_version={version}, using defaults")
                return

            with self._rlock:
                # 只恢复已知顶层键
                for key in ("current_app", "apps", "source_configs"):
                    if key in migrated:
                        self._state[key] = migrated[key]
                # device_settings 单独处理：先 sanitize 再合并到默认值之上，
                # 保证非法 key / 非法 orientation 不进内存，且默认值不因过滤而丢失。
                if "device_settings" in migrated:
                    sanitized = self._sanitize_device_settings(migrated["device_settings"])
                    self._state["device_settings"].update(sanitized)
                self._state["schema_version"] = 1
                self._state["dirty"] = True

                # 升级兼容：补齐旧版本 state 中缺失的 app 条目（以默认值填入）。
                # 保证 system_status 等新 app 在旧 state.json 升级后自动可用，
                # 同时不覆盖已有 app 的用户配置。
                defaults = _default_state()
                for app_id, default_cfg in defaults["apps"].items():
                    if app_id not in self._state["apps"]:
                        log.info(
                            f"State upgrade: adding missing app '{app_id}' with defaults"
                        )
                        self._state["apps"][app_id] = copy.deepcopy(default_cfg)

                _normalize_source_configs(self._state["source_configs"])

                # 校验 current_app：对照 catalog 的 KNOWN_APP_IDS 校验，而不是
                # self._state["apps"].keys()，避免持久化中的 unknown app 条目被误认为合法。
                if self._state["current_app"] not in KNOWN_APP_IDS:
                    log.warning(
                        f"Loaded current_app='{self._state['current_app']}' is not in "
                        f"known apps {KNOWN_APP_IDS}; falling back to '{DEFAULT_APP_ID}'"
                    )
                    self._state["current_app"] = DEFAULT_APP_ID

            log.info(f"State loaded from {path} (schema_version={version or 'v0→v1'})")
        except Exception as e:
            log.error(f"State load failed: {e}")


# 模块级单例
app_state = AppState()
