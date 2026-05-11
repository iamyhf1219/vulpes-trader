"""测试参数扫描优化器"""

import pandas as pd
import numpy as np
from datetime import datetime
from vulpes_trader.backtest.optimizer import ParameterSweep, ParamResult
from vulpes_trader.backtest.engine import BacktestResult, BacktestTrade, BacktestEngine


def _make_data(n=200):
    np.random.seed(42)
    prices = [50000.0]
    for _ in range(n - 1):
        prices.append(prices[-1] * (1 + np.random.normal(0, 0.01)))
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=n, freq="1h"),
        "open": prices, "high": prices, "low": prices,
        "close": prices, "volume": np.random.uniform(100, 1000, n),
    })


def _sma_strategy(df, fast=5, slow=20):
    if len(df) < slow + 1:
        return None
    close = df["close"].values
    f = pd.Series(close).rolling(fast).mean()
    s = pd.Series(close).rolling(slow).mean()
    if len(f) < 2 or pd.isna(f.iloc[-2]) or pd.isna(s.iloc[-2]):
        return None
    if f.iloc[-2] <= s.iloc[-2] and f.iloc[-1] > s.iloc[-1]:
        return {"direction": "long", "confidence": 0.7}
    if f.iloc[-2] >= s.iloc[-2] and f.iloc[-1] < s.iloc[-1]:
        return {"direction": "short", "confidence": 0.7}
    return None


class TestParamResult:
    def test_score_with_trades(self):
        r = ParamResult(
            params={"fast": 5},
            result=BacktestResult(
                trades=[BacktestTrade(symbol="T", side="long", entry_time=datetime(2026,1,1), pnl=10)],
                equity_curve=[100, 110],
            ),
        )
        # 3 trades minimum requirement → score = -999
        assert r.score == -999

    def test_score_calculation(self):
        trades = [BacktestTrade(symbol="T", side="long", entry_time=datetime(2026,1,1), pnl=10) for _ in range(10)]
        eq = [100 + i for i in range(50)]
        r = ParamResult(
            params={"fast": 5},
            result=BacktestResult(trades=trades, equity_curve=eq),
        )
        assert r.score > 0

    def test_better_score_wins(self):
        good = ParamResult(params={"f": 5}, result=BacktestResult(
            trades=[BacktestTrade(symbol="T", side="long", entry_time=datetime(2026,1,1), pnl=10) for _ in range(20)],
            equity_curve=[100 + i * 2 for i in range(50)],
        ))
        bad = ParamResult(params={"f": 20}, result=BacktestResult(
            trades=[BacktestTrade(symbol="T", side="long", entry_time=datetime(2026,1,1), pnl=-10) for _ in range(3)],
            equity_curve=[100] + [95] * 49,
        ))
        assert good.score > bad.score


class TestParameterSweep:
    def test_grid_scan(self):
        sweep = ParameterSweep(
            signal_fn=_sma_strategy,
            param_grid={"fast": [5, 10], "slow": [20, 50]},
            engine_kwargs={"capital": 10000, "leverage": 1},
        )
        data = _make_data(300)
        results = sweep.run(data, top_n=3, progress=False)
        assert len(results) <= 3
        assert len(results) > 0

    def test_results_sorted_by_score(self):
        sweep = ParameterSweep(
            signal_fn=_sma_strategy,
            param_grid={"fast": [3, 5, 10], "slow": [20, 50]},
            engine_kwargs={"capital": 10000, "leverage": 1},
        )
        data = _make_data(400)
        results = sweep.run(data, top_n=5, progress=False)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_empty_grid(self):
        sweep = ParameterSweep(
            signal_fn=_sma_strategy,
            param_grid={},
            engine_kwargs={"capital": 10000},
        )
        data = _make_data(100)
        results = sweep.run(data, top_n=5, progress=False)
        assert len(results) <= 1

    def test_multi_data_support(self):
        sweep = ParameterSweep(
            signal_fn=_sma_strategy,
            param_grid={"fast": [5]},
            engine_kwargs={"capital": 10000, "leverage": 1},
            multi_data=True,
        )
        data = {"BTC": _make_data(200), "ETH": _make_data(200)}
        results = sweep.run(data, top_n=3, progress=False)
        assert len(results) > 0

    def test_run_parallel(self):
        sweep = ParameterSweep(
            signal_fn=_sma_strategy,
            param_grid={"fast": [3, 5], "slow": [20]},
            engine_kwargs={"capital": 10000, "leverage": 1},
        )
        data = _make_data(200)
        results = sweep.run_parallel(data, top_n=3)
        assert len(results) > 0
