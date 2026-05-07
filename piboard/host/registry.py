"""
Registry：启动时一次性构建的 App / Source / Binding 类注册表。

性能说明：
- 所有注册发生在启动阶段，主循环中只做 dict 查找（O(1)）。
- 不做动态模块扫描、反射或热加载。

本轮限制：
- Source / Binding 注册接口已定义，本轮未接入运行路径（静态脚手架）。
- 多 App 切换通过 registry 路由的机制推迟到后续 Task。
"""
from typing import Dict, Type


class Registry:

    def __init__(self):
        self._apps: Dict[str, Type] = {}
        self._sources: Dict[str, Type] = {}
        self._bindings: Dict[str, Type] = {}

    # ------------------------------------------------------------------
    # Apps
    # ------------------------------------------------------------------

    def register_app(self, app_id: str, cls: Type) -> None:
        self._apps[app_id] = cls

    def get_app(self, app_id: str) -> Type:
        if app_id not in self._apps:
            raise KeyError(f"App '{app_id}' not registered")
        return self._apps[app_id]

    def list_apps(self) -> list:
        return list(self._apps.keys())

    # ------------------------------------------------------------------
    # Sources（静态脚手架，本轮未接入运行路径）
    # ------------------------------------------------------------------

    def register_source(self, source_id: str, cls: Type) -> None:
        self._sources[source_id] = cls

    def get_source(self, source_id: str) -> Type:
        if source_id not in self._sources:
            raise KeyError(f"Source '{source_id}' not registered")
        return self._sources[source_id]

    def list_sources(self) -> list:
        return list(self._sources.keys())

    # ------------------------------------------------------------------
    # Bindings（静态脚手架，本轮未接入运行路径）
    # ------------------------------------------------------------------

    def register_binding(self, binding_id: str, cls: Type) -> None:
        self._bindings[binding_id] = cls

    def get_binding(self, binding_id: str) -> Type:
        if binding_id not in self._bindings:
            raise KeyError(f"Binding '{binding_id}' not registered")
        return self._bindings[binding_id]

    def list_bindings(self) -> list:
        return list(self._bindings.keys())


# 模块级单例：启动时填充一次，主循环零开销
registry = Registry()
