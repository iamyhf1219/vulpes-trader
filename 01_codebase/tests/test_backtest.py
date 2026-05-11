"""测试回测引擎"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from vulpes_trader.backtest.engine import BacktestEngine, BacktestResult, BacktestTrade


def _make_ohlcv(n=200, start_price=50000.0, volatility=0.01):
    """生成模拟 OHLCV 数据"""
    np.random.seed(42)
    ts = pd.date_range("2026-01-01", periods=n, freq="1h")
    prices = [start_price]
    for _ in range(n - 1):
        prices.append(prices[-1] * (1 + np.random.normal(0, volatility)))
    prices = np.array(prices)
    df = pd.DataFrame({
        "timestamp": ts,
        "open": prices,
        "high": prices * (1 + abs(np.random.normal(0, volatility * 0.5, n))),
        "low": prices * (1 - abs(np.random.normal(0, volatility * 0.5, n))),
        "close": prices,
        "volume": np.random.uniform(100, 1000, n),
    })
    return df


def _sma_cross_signal(ohlcv_slice, fast=5, slow=20):
    """简单 SMA 金叉死叉信号"""
    if len(ohlcv_slice) < slow:
        return None
    close = ohlcv_slice["close"].values
    sma_fast = pd.Series(close).rolling(fast).mean().iloc[-1]
    sma_slow = pd.Series(close).rolling(slow).mean().iloc[-1]
    prev_fast = pd.Series(close).rolling(fast).mean().iloc[-2]
    prev_slow = pd.Series(close).rolling(slow).mean().iloc[-2]
    if prev_fast <= prev_slow and sma_fast > sma_slow:
        return {"direction": "long", "confidence": 0.7}
    if prev_fast >= prev_slow and sma_fast < sma_slow:
        return {"direction": "short", "confidence": 0.7}
    return None


def test_backtest_result_empty():
    """空回测结果"""
    r = BacktestResult()
    assert r.total_trades == 0
    assert r.win_rate == 0.0
    assert r.total_pnl == 0.0
    assert r.sharpe_ratio == 0.0
    assert r.max_drawdown == 0.0


def test_backtest_result_with_trades():
    """有交易的回测结果属性计算"""
    trades = [
        BacktestTrade(symbol="BTC", side="long", entry_time=datetime(2026,1,1),
                      exit_time=datetime(2026,1,2), entry_price=100, exit_price=110,
                      quantity=1, leverage=1, pnl=10.0),
        BacktestTrade(symbol="BTC", side="short", entry_time=datetime(2026,1,3),
                      exit_time=datetime(2026,1,4), entry_price=110, exit_price=100,
                      quantity=1, leverage=1, pnl=10.0),
        BacktestTrade(symbol="BTC", side="long", entry_time=datetime(2026,1,5),
                      exit_time=datetime(2026,1,6), entry_price=100, exit_price=95,
                      quantity=1, leverage=1, pnl=-5.0),
    ]
    equity = [10000, 10010, 10020, 10015]
    r = BacktestResult(trades=trades, equity_curve=equity,
                       timestamps=[datetime(2026,1,d) for d in range(1,5)])
    assert r.total_trades == 3
    assert r.win_trades == 2
    assert r.loss_trades == 1
    assert r.win_rate == 2/3 * 100
    assert r.total_pnl == 15.0


def test_backtest_result_sharpe():
    """夏普比率计算"""
    # 稳定上涨的权益曲线
    equity = [10000 + i * 10 for i in range(100)]
    r = BacktestResult(equity_curve=equity,
                       timestamps=[datetime(2026,1,1) + timedelta(hours=i) for i in range(100)])
    assert r.sharpe_ratio > 0


def test_backtest_result_max_dd():
    """最大回撤"""
    equity = [100, 110, 120, 90, 80, 130, 140]
    r = BacktestResult(equity_curve=equity,
                       timestamps=[datetime(2026,1,d) for d in range(1,8)])
    # peak=120, trough=80, dd=40/120=33.3%
    assert 30 < r.max_drawdown < 40


def test_backtest_result_report():
    """回测报告生成"""
    r = BacktestResult(trades=[], equity_curve=[10000])
    report = r.report()
    assert "Backtest Report" in report
    assert "Total Trades" in report


def test_backtest_engine_empty_data():
    """空数据回测"""
    df = _make_ohlcv(n=10)  # 数据太少，SMA无法生成信号
    engine = BacktestEngine(signal_fn=_sma_cross_signal, capital=10000)
    result = engine.run(df)
    assert result.total_trades == 0


def test_backtest_engine_sma_cross():
    """SMA 金叉死叉策略回测"""
    df = _make_ohlcv(n=500, start_price=50000)
    engine = BacktestEngine(signal_fn=_sma_cross_signal, capital=10000, leverage=1)
    result = engine.run(df)
    assert result.total_trades > 0
    assert len(result.equity_curve) > 0
    assert len(result.timestamps) > 0
    # 检查 report 输出
    report = result.report()
    assert "Trades" in report


def test_backtest_engine_positions_limit():
    """最大持仓限制"""
    def bullish_signal(df):
        return {"direction": "long", "confidence": 0.9}
    df = _make_ohlcv(n=100)
    engine = BacktestEngine(signal_fn=bullish_signal, capital=10000, max_positions=2)
    result = engine.run(df)
    assert result.total_trades > 0


def test_backtest_engine_equity_curve():
    """权益曲线长度"""
    df = _make_ohlcv(n=100)
    engine = BacktestEngine(signal_fn=_sma_cross_signal, capital=10000)
    result = engine.run(df)
    assert len(result.equity_curve) == len(df)
    assert len(result.timestamps) == len(df)
