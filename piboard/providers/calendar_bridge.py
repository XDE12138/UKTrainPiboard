"""
CalendarSourceBridge：将 CalendarSource + CalendarToUKBinding 包装为 BaseProvider 兼容接口。

职责边界：
- 对外：呈现与旧 CalendarProvider 完全相同的 BaseProvider 接口
  （provider_id="calendar"，fetch，get_config_schema，update_config）
- 对内：统一走新链路 CalendarSource → CalendarToUKBinding
  - not ical_url  → CalendarSource._mock_data()
  - 有 ical_url   → CalendarSource._live_data()（异常 fail-loud）

不做的事：
- 不解析任何 iCal 数据
- 不构造 BoardContent 行内容
- 不管理刷新调度，不负责 config 持久化

get_config_schema() 复用旧 CalendarProvider().get_config_schema()，避免两处 schema 漂移。

回滚方案：在 main.py 把 CalendarSourceBridge 换回 CalendarProvider 即可，无其他依赖。
"""
from providers.base import BaseProvider
from providers.calendar_provider import CalendarProvider
from sources.calendar import CalendarSource
from bindings.calendar_to_uk import CalendarToUKBinding
from board.content import BoardContent


class CalendarSourceBridge(BaseProvider):
    """
    兼容桥接层：对现有系统呈现与旧 CalendarProvider 相同的接口，
    mock 和 live 路径均走新链路 CalendarSource → CalendarToUKBinding。
    """

    provider_id = "calendar"
    display_name = "Calendar"
    default_refresh_interval = 300  # 5分钟，与旧 CalendarProvider 一致

    def __init__(self, config: dict = None):
        super().__init__(config)
        self._source  = CalendarSource(config=self.config)
        self._binding = CalendarToUKBinding()

    # ------------------------------------------------------------------
    # BaseProvider 接口
    # ------------------------------------------------------------------

    def fetch(self) -> BoardContent:
        """
        统一走新链路：CalendarSource.fetch() → CalendarToUKBinding.transform()。
        mock / live 路由由 CalendarSource 内部按 ical_url 决定。
        """
        raw = self._source.fetch()
        return self._binding.transform(raw)

    def get_config_schema(self) -> dict:
        """直接复用旧 CalendarProvider 的 schema，避免两处维护漂移。"""
        return CalendarProvider().get_config_schema()

    def update_config(self, new_config: dict):
        """同步更新 bridge 和 source 的 config。"""
        super().update_config(new_config)
        self._source.config = self.config
