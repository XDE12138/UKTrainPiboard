"""
TrainSourceBridge：将 TrainSource + TrainToUKBinding 包装为 BaseProvider 兼容接口。

职责边界：
- 对外：呈现与旧 TrainProvider 完全相同的 BaseProvider 接口
  （provider_id="train"，fetch，get_config_schema，update_config）
- 对内：
  - data_source == "mock"  → 走新链路（TrainSource → TrainToUKBinding）
  - data_source != "mock"  → 显式委托旧 TrainProvider.fetch()（整体，不调用私有方法）

不做的事：
- 不解析任何 API 响应
- 不构造 BoardContent 行内容
- 不调用旧 TrainProvider 的任何私有方法
- 不管理刷新调度，不负责 config 持久化

get_config_schema() 直接复用旧 TrainProvider().get_config_schema()，
避免两处 schema 漂移。

回滚方案：在 main.py 把 TrainSourceBridge 换回 TrainProvider 即可，无其他依赖。
"""
from providers.base import BaseProvider
from providers.train import TrainProvider
from sources.train import TrainSource
from bindings.train_to_uk import TrainToUKBinding
from board.content import BoardContent


class TrainSourceBridge(BaseProvider):
    """
    兼容桥接层：对现有系统呈现与旧 TrainProvider 相同的接口，
    对 mock 路径启用新 Source → Binding 链路。
    """

    provider_id = "train"
    display_name = "Train Departures"
    default_refresh_interval = 60

    def __init__(self, config: dict = None):
        super().__init__(config)
        self._source = TrainSource(config=self.config)
        self._binding = TrainToUKBinding()
        # live 路径显式回退：整体委托旧 TrainProvider，不感知其内部实现
        self._fallback = TrainProvider(config=self.config)

    # ------------------------------------------------------------------
    # BaseProvider 接口
    # ------------------------------------------------------------------

    def fetch(self) -> BoardContent:
        """
        mock 路径：走新链路 TrainSource → TrainToUKBinding。
        其他路径：委托旧 TrainProvider.fetch()，接触点仅为 fetch()。
        """
        data_source = self.config.get("data_source", "mock")
        if data_source == "mock":
            raw = self._source.fetch()
            return self._binding.transform(raw)
        else:
            return self._fallback.fetch()

    def get_config_schema(self) -> dict:
        """直接复用旧 TrainProvider 的 schema，避免两处维护漂移。"""
        return TrainProvider().get_config_schema()

    def update_config(self, new_config: dict):
        """同步更新 bridge、source、fallback 三者的 config，避免遗漏。"""
        super().update_config(new_config)
        self._source.config = self.config
        self._fallback.config = self.config
