"""
后台数据拉取调度器。

- 每个 Provider 按自己的 default_refresh_interval 独立调度
- ThreadPoolExecutor(max_workers=2)，避免 Zero 2W 过载
- 失败时保留上次缓存，记录日志，不崩溃
"""
import threading
import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor
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
        self._lock = threading.RLock()
        self._inflight = {}
        self._pending = {}
        self._stopped = threading.Event()

    # ------------------------------------------------------------------
    # Provider 管理
    # ------------------------------------------------------------------

    def register(self, provider: BaseProvider):
        with self._lock:
            self._providers[provider.provider_id] = provider
            self._last_fetch[provider.provider_id] = 0.0
        log.info(f"Registered provider: {provider.provider_id}")

    def unregister(self, provider_id: str):
        with self._lock:
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
        with self._lock:
            self._running = False
            self._stopped.set()
            for future in self._pending.values():
                future.cancel()
            self._pending.clear()
        if self._thread is not None:
            self._thread.join()
        self._executor.shutdown(wait=False)
        log.info("DataFetcher stopped")

    def force_refresh(self, provider_id: str):
        """Web 端触发立即刷新某个 Provider。"""
        with self._lock:
            if self._stopped.is_set() or provider_id not in self._providers:
                return None
            if provider_id in self._inflight:
                # 保留一次后续刷新，确保正在请求时修改的配置最终生效。
                return self._pending.setdefault(provider_id, Future())
            return self._submit(provider_id)

    def _submit(self, provider_id, future=None):
        """调用方持有 _lock；每个数据源最多一个请求和一次后续刷新。"""
        future = future if future is not None else Future()
        self._inflight[provider_id] = future
        self._last_fetch[provider_id] = time.monotonic()
        self._executor.submit(self._run_fetch, self._providers[provider_id], future)
        return future

    def _run_fetch(self, provider, future):
        if future.set_running_or_notify_cancel():
            future.set_result(self._do_fetch(provider))
        with self._lock:
            pid = provider.provider_id
            self._inflight.pop(pid, None)
            pending = self._pending.pop(pid, None)
            if pending is not None:
                if not self._stopped.is_set() and pid in self._providers:
                    self._submit(pid, pending)
                else:
                    pending.cancel()

    # ------------------------------------------------------------------
    # 调度循环
    # ------------------------------------------------------------------

    def _loop(self):
        while self._running:
            with self._lock:
                if self._stopped.is_set():
                    break
                now = time.monotonic()
                for pid, provider in self._providers.items():
                    last = self._last_fetch.get(pid, 0.0)
                    interval = self._safe_refresh_interval(provider)
                    if pid not in self._inflight and now - last >= interval:
                        self._submit(pid)
            self._stopped.wait(1)  # 可在停止时立即唤醒

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
