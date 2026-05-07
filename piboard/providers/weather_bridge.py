"""
WeatherSourceBridge：将 WeatherSource + WeatherToUKBinding 包装为 BaseProvider 兼容接口。

职责边界：
- 对外：呈现与旧 WeatherProvider 完全相同的 BaseProvider 接口
  （provider_id="weather"，fetch，get_config_schema，update_config）
- 对内：
  - 默认无 API key 走 Open-Meteo live 路径（WeatherSource → WeatherToUKBinding）
  - 有 OpenWeatherMap API key 时保留旧 WeatherProvider fallback

不做的事：
- 不解析任何 API 响应
- 不构造 BoardContent 行内容
- 不调用旧 WeatherProvider 的任何私有方法（_mock_content / _fetch_owm）
- 不管理刷新调度，不负责 config 持久化

get_config_schema() 直接复用旧 WeatherProvider().get_config_schema()，
避免两处 schema 漂移。

回滚方案：在 main.py 把 WeatherSourceBridge 换回 WeatherProvider 即可，无其他依赖。
"""
from providers.base import BaseProvider
from providers.weather import WeatherProvider
from sources.weather import WeatherSource
from bindings.weather_to_uk import WeatherToUKBinding
from board.content import BoardContent


class WeatherSourceBridge(BaseProvider):
    """
    兼容桥接层：对现有系统呈现与旧 WeatherProvider 相同的接口，
    对无 api_key 路径启用 Open-Meteo Source → Binding 链路。
    """

    provider_id = "weather"
    display_name = "Weather"
    default_refresh_interval = 600  # 10分钟，与旧 WeatherProvider 一致

    def __init__(self, config: dict = None):
        super().__init__(config)
        self._source   = WeatherSource(config=self.config)
        self._binding  = WeatherToUKBinding()
        # live 路径显式回退：整体委托旧 WeatherProvider，不感知其内部实现
        self._fallback = WeatherProvider(config=self.config)

    # ------------------------------------------------------------------
    # BaseProvider 接口
    # ------------------------------------------------------------------

    def fetch(self) -> BoardContent:
        """
        无 api_key：走 Open-Meteo WeatherSource → WeatherToUKBinding。
        live 路径（有 api_key）：委托旧 WeatherProvider.fetch()，接触点仅为 fetch()。
        """
        api_key = self.config.get("api_key", "")
        if not api_key:
            raw = self._source.fetch()
            return self._binding.transform(raw)
        return self._fallback.fetch()

    def get_config_schema(self) -> dict:
        """直接复用旧 WeatherProvider 的 schema，避免两处维护漂移。"""
        return WeatherProvider().get_config_schema()

    def update_config(self, new_config: dict):
        """同步更新 bridge、source、fallback 三者的 config，避免遗漏。"""
        super().update_config(new_config)
        self._source.config   = self.config
        self._fallback.config = self.config
