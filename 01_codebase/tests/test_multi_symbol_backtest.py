"""测试多币种回测运行器"""

import pytest
import pandas as pd
import numpy as np
from vulpes_trader.backtest.multi_symbol import (
    MultiSymbolBacktest, compute_score, CombinedResult,
)
from vulpes_trader.backtest.engine import BacktestResult, BacktestTrade


@pytest.fixture
def dummy_data():
    """为 BTC 和 ETH 生成模拟 K 线"""
    np.random.seed(42)
    n = 500
    data = {}
    for symbol in ["BTC/USDT:USDT", "ETH/USDT:USDT"]:
        closes = 100 + np.cumsum(np.random.randn(n) * 0.5)
        data[symbol] = pd.DataFrame({
            "timestamp": pd.date_range("2026-01-01", periods=n, freq="5min").astype(int) // 10**6,
            "open": closes * 0.995,
            "high": closes * 1.01,
            "low": closes * 0.99,
            "close": closes,
            "volume": np.random.rand(n) * 100,
        })
    return data


def dummy_signal_builder(symbol: str):
    """模拟信号函数"""
    def signal_fn(df):
        closes = df["close"].values
        if len(closes) < 50:
            return None
        from vulpes_trader.signal.trend_follower import TrendFollower

        class MockK:
            def get_klines(self, s, t):
                return df
        trend = TrendFollower(MockK(), symbol=symbol)
        fast_val = trend._ema(closes, trend.ema_fast[0])[-1]
        slow_val = trend._ema(closes, trend.ema_slow[0])[-1]
        if fast_val > slow_val:
            return {"direction": "long", "confidence": 0.6}
        else:
            return {"direction": "short", "confidence": 0.6}
    return signal_fn


def test_compute_score():
    """评分函数正确处理"""
    # 构建有波动的向上 equity curve
    np.random.seed(42)
    eq = [100.0]
    for i in range(30):
        eq.append(eq[-1] * (1.003 + np.random.uniform(-0.01, 0.01)))
    result = BacktestResult(
        trades=[BacktestTrade(symbol="BTC", side="long", entry_time=None,
                              entry_price=100, exit_price=110, pnl=10, pnl_pct=0.1)
                for _ in range(20)],
        equity_curve=eq,
        timestamps=[],
    )
    score = compute_score(result)
    assert score > 0
    assert result.sharpe_ratio > 0


def test_multi_symbol_run(dummy_data):
    """多币种回测跑通"""
    msb = MultiSymbolBacktest(
        signal_fn_builder=dummy_signal_builder,
        engine_kwargs={"capital": 10000},
        min_trades=3,
    )
    result = msb.run(dummy_data)
    assert isinstance(result, CombinedResult)
    assert len(result.symbol_results) == 2


def test_combined_score_penalty(dummy_data):
    """交易不足的币种有惩罚"""
    msb = MultiSymbolBacktest(
        signal_fn_builder=dummy_signal_builder,
        engine_kwargs={"capital": 10000},
        min_trades=999,  # 所有币种都不达标
    )
    result = msb.run(dummy_data)
    assert isinstance(result, CombinedResult)
    assert result.combined_score == -999
