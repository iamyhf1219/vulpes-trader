import pytest
import pandas as pd
from vulpes_trader.signal.trend_follower import TrendFollower
from vulpes_trader.signal.base import SignalGenerator, Signal, SignalDirection


class MockKlineEngine:
    """模拟 K 线引擎"""
    def __init__(self, closes: list):
        timestamps = [1700000000000 + i * 300000 for i in range(len(closes))]
        self._df = pd.DataFrame({
            "timestamp": timestamps,
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
            "volume": [100] * len(closes),
        })

    def get_klines(self, symbol: str, timeframe: str):
        return self._df


def test_trend_follower_init():
    """测试 TrendFollower 初始化"""
    engine = MockKlineEngine([50000] * 100)
    tf = TrendFollower(engine)
    assert tf.name() == "trend"


def test_trend_follower_generate_upward():
    """测试上升趋势生成做多信号"""
    # 构造上升趋势数据
    closes = [50000 + i * 20 for i in range(100)]
    engine = MockKlineEngine(closes)
    tf = TrendFollower(engine)
    
    import asyncio
    signal = asyncio.run(tf.generate("BTC/USDT"))
    
    if signal:
        assert signal.symbol == "BTC/USDT"
        assert signal.direction in (SignalDirection.LONG,)
        assert signal.source == "trend"
        assert 0 < signal.confidence <= 1.0


def test_trend_follower_generate_downward():
    """测试下降趋势生成做空信号"""
    closes = [50000 - i * 20 for i in range(100)]
    engine = MockKlineEngine(closes)
    tf = TrendFollower(engine)
    
    import asyncio
    signal = asyncio.run(tf.generate("BTC/USDT"))
    
    if signal:
        assert signal.direction in (SignalDirection.SHORT, SignalDirection.EXIT_SHORT)


def test_signal_is_tradeable():
    """测试 Signal.is_tradeable"""
    s1 = Signal(symbol="BTC", direction=SignalDirection.LONG, 
                confidence=0.8, source="test", timestamp=1700000000)
    assert s1.is_tradeable()
    
    s2 = Signal(symbol="BTC", direction=SignalDirection.NEUTRAL,
                confidence=0.8, source="test", timestamp=1700000000)
    assert not s2.is_tradeable()
    
    s3 = Signal(symbol="BTC", direction=SignalDirection.LONG,
                confidence=0.3, source="test", timestamp=1700000000)
    assert not s3.is_tradeable(min_confidence=0.5)


class DummyKlineEngine:
    """最小化模拟 K 线引擎"""
    def get_klines(self, symbol, timeframe):
        import pandas as pd
        import numpy as np
        n = 100
        closes = 100 + np.cumsum(np.random.randn(n) * 0.5)
        return pd.DataFrame({
            "timestamp": pd.date_range("2026-01-01", periods=n, freq="5min").astype(int) // 10**6,
            "open": closes * 0.995, "high": closes * 1.01,
            "low": closes * 0.99, "close": closes,
            "volume": np.random.rand(n) * 100,
        })


@pytest.mark.asyncio
async def test_trend_with_symbol_config():
    """不同币种使用不同参数"""
    kline = DummyKlineEngine()
    btc = TrendFollower(kline, symbol="BTC/USDT:USDT")
    assert btc.ema_fast == [9, 12]
    assert btc.ema_slow == [26, 50]
    sol = TrendFollower(kline, symbol="SOL/USDT:USDT")
    assert sol.ema_fast == [12, 15]


@pytest.mark.asyncio
async def test_trend_with_atr_adaptation():
    """有波动率数据时 EMA 周期会自适应调整"""
    kline = DummyKlineEngine()
    tf = TrendFollower(kline, symbol="BTC/USDT:USDT")
    tf._volatility._atr_history = [1.0] * 144
    high_atr = 3.5
    adjusted = tf._volatility.adaptive_ema_period(12, high_atr)
    assert adjusted < 12


def test_ema_calculation():
    """测试 EMA 计算"""
    prices = [10, 12, 15, 14, 13, 16, 18, 17, 19, 21]
    ema_values = TrendFollower._ema(prices, 5)
    assert len(ema_values) == len(prices) - 5 + 1
    assert ema_values[-1] > ema_values[0]  # 上升趋势
