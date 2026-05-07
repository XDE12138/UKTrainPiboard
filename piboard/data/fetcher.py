"""
后台数据拉取调度器。

- 每个 Provider 按自己的 default_refresh_interval 独立调度
- ThreadPoolExecutor(max_workers=2)，避免 Zero 2W 过载
- 失败时保留上次缓存，记录日志，不崩溃
"""
import threading
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict
from providers.base import BaseProvider
from state import app_state

log = logging.getLogger(__name__)


class DataFetcher:

    def __init__(self):
        self._providers: Dict[str, BaseProvider] = {}
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._last_fetch: Dict[str, float] = {}
        self._running = False
        self._thread: threading.Thread = None

    # ------------------------------------------------------------------
    # Provider 管理
    # ------------------------------------------------------------------

    def register(self, provider: BaseProvider):
        self._providers[provider.provider_id] = provider
        self._last_fetch[provider.provider_id] = 0.0
        log.info(f"Registered provider: {provider.provider_id}")

    def unregister(self, provider_id: str):
        self._providers.pop(provider_id, None)
        self._last_fetch.pop(provider_id, None)

    # ------------------------------------------------------------------
    # 调度控制
    # ------------------------------------------------------------------

    def start(self):
        """启动后台调度线程。"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="DataFetcher")
        self._thread.start()
        log.info("DataFetcher started")

    def stop(self):
        self._running = False
        self._executor.shutdown(wait=False)
        log.info("DataFetcher stopped")

    def force_refresh(self, provider_id: str):
        """Web 端触发立即刷新某个 Provider。"""
        provider = self._providers.get(provider_id)
        if provider is not None:
            self._last_fetch[provider_id] = time.time()
            future = self._executor.submit(self._do_fetch, provider)
            log.info(f"Force refresh: {provider_id}")
            return future
        return None

    # ------------------------------------------------------------------
    # 调度循环
    # ------------------------------------------------------------------

    def _loop(self):
        while self._running:
            now = time.time()
            for pid, provider in list(self._providers.items()):
                last = self._last_fetch.get(pid, 0.0)
                interval = self._safe_refresh_interval(provider)
                if now - last >= interval:
                    self._last_fetch[pid] = now
                    self._executor.submit(self._do_fetch, provider)
            time.sleep(1)  # 调度精度 1 秒

    def _safe_refresh_interval(self, provider: BaseProvider) -> float:
        try:
            interval = float(provider.get_refresh_interval())
        except (TypeError, ValueError):
            interval = float(provider.default_refresh_interval)
        return max(1.0, interval)

    def _do_fetch(self, provider: BaseProvider):
        try:
            content = provider.fetch()
            provider._cached_content = content
            app_state.set_dirty(True)
            log.debug(f"Fetched: {provider.provider_id}")
            return True
        except Exception as e:
            log.error(f"Fetch failed [{provider.provider_id}]: {e}")
            # 保留上次缓存，不重置
            return False
