from abc import ABC, abstractmethod
from board.content import BoardContent
from typing import Optional, Dict, Any


class BaseProvider(ABC):

    provider_id: str = "base"            # 唯一标识，用于注册和 Web 端引用
    display_name: str = "Base Provider"  # Web 控制台显示名称
    default_refresh_interval: int = 60   # 默认刷新间隔（秒）

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._cached_content: Optional[BoardContent] = None

    @abstractmethod
    def fetch(self) -> BoardContent:
        """
        拉取/生成内容，返回 BoardContent。
        此方法在后台线程中调用，可以做网络请求、读文件等。
        不要在此方法中调用任何 pygame API。
        """
        ...

    def get_content(self) -> BoardContent:
        """返回缓存内容，供渲染层调用（主线程安全）"""
        return self._cached_content or self._empty_content()

    def get_config_schema(self) -> Dict:
        """
        返回此 Provider 的配置项描述，Web 控制台据此自动生成表单。
        格式示例：
        {
            "city": {"type": "string", "label": "城市", "default": "London"},
            "units": {"type": "select", "label": "单位", "options": ["metric", "imperial"]},
            "api_key": {"type": "string", "label": "API Key", "secret": True}
        }
        """
        return {}

    def update_config(self, new_config: Dict[str, Any]):
        """更新配置，Web 端修改后调用"""
        self.config.update(new_config)

    def get_refresh_interval(self) -> float:
        """返回当前刷新间隔（秒），允许子类根据配置动态调整。"""
        return float(self.default_refresh_interval)

    def _empty_content(self) -> BoardContent:
        return BoardContent(
            title=self.display_name,
            subtitle="Loading...",
            status_text="--",
            status_color="dim",
            provider_id=self.provider_id,
        )
