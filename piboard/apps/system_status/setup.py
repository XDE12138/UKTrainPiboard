"""
system_status App 注册函数。

只做 registry 注册，不创建 Provider / Layout / Binding。
实例化由 main.py 负责。
"""
from host.registry import Registry
from apps.system_status.app import SystemStatusApp


def setup(registry: Registry) -> None:
    """将 SystemStatusApp 注册到 Registry。"""
    registry.register_app("system_status", SystemStatusApp)
