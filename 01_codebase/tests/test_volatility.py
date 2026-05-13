"""测试波动率自适应模块"""

import pytest
import pandas as pd
import numpy as np
from vulpes_trader.data.volatility import VolatilityAdapter


@pytest.fixture
def sample_df():
    """构造 100 根模拟 K 线"""
    np.random.seed(42)
    n = 100
    closes = 100 + np.cumsum(np.random.randn(n) * 0.5)
    highs = closes * 1.01
    lows = closes * 0.99
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=n, freq="5min").astype(int) // 10**6,
        "open": closes * 0.995,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": np.random.rand(n) * 100,
    })


def test_compute_atr_returns_pct(sample_df):
    """ATR 返回百分比值"""
    va = VolatilityAdapter(period=14)
    atr = va.compute_atr(sample_df)
    assert atr is not None
    assert 0.1 < atr < 5.0  # 合理范围


def test_compute_atr_short_data():
    """数据不足返回 None"""
    va = VolatilityAdapter(period=14)
    short = pd.DataFrame({"high": [100], "low": [99], "close": [99.5]})
    assert va.compute_atr(short) is None


def test_adaptive_ema_period_variation(sample_df):
    """高波动缩短 EMA 周期，低波动延长"""
    va = VolatilityAdapter(period=14)
    atr = va.compute_atr(sample_df)

    # 高波动百分位
    va._atr_history = [0.5] * 100 + [atr]  # 模拟历史
    high_pct = va.get_atr_percentile(atr)
    adjusted = va.adaptive_ema_period(12, atr)
    assert adjusted <= 12  # 不增反减
    assert adjusted >= 3   # 下限


def test_adaptive_position_size(sample_df):
    """高 ATR 减小仓位"""
    va = VolatilityAdapter()
    size_low = va.adaptive_position_size(0.15, atr_pct=0.5)
    size_high = va.adaptive_position_size(0.15, atr_pct=5.0)
    assert size_high < size_low


def test_adaptive_stop_loss(sample_df):
    """高 ATR 放宽止损"""
    va = VolatilityAdapter()
    sl_low = va.adaptive_stop_loss(0.05, atr_pct=0.5)
    sl_high = va.adaptive_stop_loss(0.05, atr_pct=5.0)
    assert sl_high >= sl_low
