"""K 线引擎和数据缓存测试"""

import pytest
import pandas as pd
from vulpes_trader.data.kline_engine import KlineEngine
from vulpes_trader.data.cache import DataCache


def test_kline_update():
    """测试 K 线更新"""
    engine = KlineEngine(cache_size=100)
    ohlcv = [1700000000000, 50000.0, 51000.0, 49000.0, 50500.0, 100.0]
    engine.update("BTC/USDT", "5m", ohlcv)

    df = engine.get_klines("BTC/USDT", "5m")
    assert len(df) == 1
    assert df.iloc[-1]["close"] == 50500.0


def test_kline_multiple_updates():
    """测试多根 K 线"""
    engine = KlineEngine(cache_size=100)
    engine.update("BTC/USDT", "5m", [1700000000000, 50000, 51000, 49000, 50500, 100])
    engine.update("BTC/USDT", "5m", [1700000005000, 50500, 51500, 50000, 51000, 150])
    assert len(engine.get_klines("BTC/USDT", "5m")) == 2


def test_kline_latest():
    """测试获取最新 K 线"""
    engine = KlineEngine()
    engine.update("BTC/USDT", "5m", [1700000000000, 50000, 51000, 49000, 50500, 100])
    latest = engine.get_latest("BTC/USDT", "5m")
    assert latest is not None
    assert latest["close"] == 50500.0


def test_cache_set_get():
    """测试缓存设置和获取"""
    cache = DataCache()
    cache.set("key1", "value1", ttl=60)
    assert cache.get("key1") == "value1"


def test_cache_expiry():
    """测试缓存过期"""
    cache = DataCache(default_ttl=0)  # 立即过期
    cache.set("key1", "value1")
    import time
    time.sleep(0.01)
    assert cache.get("key1") is None


def test_cache_get_or_set():
    """测试 get_or_set"""
    cache = DataCache()
    result = cache.get_or_set("compute_key", lambda: "computed", ttl=60)
    assert result == "computed"

    # 第二次应该返回缓存值，不会调 factory
    called = False

    def factory():
        nonlocal called
        called = True
        return "new"

    result = cache.get_or_set("compute_key", factory, ttl=60)
    assert result == "computed"
    assert not called


def test_cache_clear():
    """测试清空缓存"""
    cache = DataCache()
    cache.set("a", 1)
    cache.set("b", 2)
    cache.clear()
    assert cache.get("a") is None
    assert cache.get("b") is None
