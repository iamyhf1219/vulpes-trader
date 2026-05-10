"""辅助数据缓存 — OI、资金费率等"""

import time
from typing import Dict, Optional, Any, Callable
import logging

logger = logging.getLogger("vulpes.cache")


class DataCache:
    """轻量级内存缓存，带 TTL 过期"""

    def __init__(self, default_ttl: int = 60):
        self.default_ttl = default_ttl
        self._data: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """设置缓存"""
        self._data[key] = value
        self._expiry[key] = time.time() + (ttl or self.default_ttl)

    def get(self, key: str) -> Optional[Any]:
        """获取缓存，过期返回 None"""
        if key not in self._data:
            return None
        if time.time() > self._expiry.get(key, 0):
            del self._data[key]
            del self._expiry[key]
            return None
        return self._data[key]

    def get_or_set(self, key: str, factory: Callable[[], Any], ttl: Optional[int] = None) -> Any:
        """获取或创建"""
        value = self.get(key)
        if value is None:
            value = factory()
            self.set(key, value, ttl)
        return value

    def clear(self):
        """清空所有缓存"""
        self._data.clear()
        self._expiry.clear()
