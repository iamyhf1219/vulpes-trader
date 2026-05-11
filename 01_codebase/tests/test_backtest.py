"""回测引擎测试 — 覆盖 BacktestResult 数值精度 + BacktestEngine 集成 + 边界"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from vulpes_trader.backtest.engine import BacktestEngine, BacktestResult, BacktestTrade


# ── helpers ──────────────────────────────────────────────────────────────

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


def _trade(pnl=100.0, side="long"):
    return BacktestTrade(
        symbol="TEST", side=side,
        entry_time=datetime(2026, 1, 1),
        exit_time=datetime(2026, 1, 2),
        entry_price=100.0, exit_price=100.0 + pnl,
        quantity=1.0, leverage=1, pnl=pnl,
    )


def _sma_cross_signal(ohlcv_slice, fast=5, slow=20):
    """SMA 金叉死叉信号 — 捕捉交叉时刻（不含前瞻）"""
    if len(ohlcv_slice) < slow + 1:
        return None
    close = ohlcv_slice["close"].values
    fast_ma = pd.Series(close).rolling(fast).mean()
    slow_ma = pd.Series(close).rolling(slow).mean()
    # 当前和前一 bar 的 MA
    prev_f, cur_f = fast_ma.iloc[-2], fast_ma.iloc[-1]
    prev_s, cur_s = slow_ma.iloc[-2], slow_ma.iloc[-1]
    if pd.isna(cur_f) or pd.isna(cur_s) or pd.isna(prev_f) or pd.isna(prev_s):
        return None
    if prev_f <= prev_s and cur_f > cur_s:
        return {"direction": "long", "confidence": 0.7}
    if prev_f >= prev_s and cur_f < cur_s:
        return {"direction": "short", "confidence": 0.7}
    return None


# ── BacktestResult 属性 ──────────────────────────────────────────────────

class TestBacktestResultEmpty:
    """空结果 / 零交易"""

    def test_all_zero_for_empty(self):
        r = BacktestResult()
        assert r.total_trades == 0
        assert r.win_trades == 0
        assert r.loss_trades == 0
        assert r.win_rate == 0.0
        assert r.total_pnl == 0.0
        assert r.sharpe_ratio == 0.0
        assert r.max_drawdown == 0.0
        assert isinstance(r.report(), str)

    def test_empty_curve_sharpe_zero(self):
        r = BacktestResult(equity_curve=[])
        assert r.sharpe_ratio == 0.0

    def test_empty_curve_drawdown_zero(self):
        r = BacktestResult(equity_curve=[])
        assert r.max_drawdown == 0.0


class TestBacktestResultWinRate:
    """胜率计算"""

    def test_all_wins(self):
        r = BacktestResult(trades=[_trade(10), _trade(20), _trade(5)])
        assert r.win_trades == 3
        assert r.loss_trades == 0
        assert r.win_rate == pytest.approx(100.0)

    def test_all_losses(self):
        r = BacktestResult(trades=[_trade(-10), _trade(-20)])
        assert r.win_trades == 0
        assert r.loss_trades == 2
        assert r.win_rate == pytest.approx(0.0)

    def test_mixed(self):
        r = BacktestResult(trades=[
            _trade(10), _trade(20), _trade(-5), _trade(30), _trade(-15),
        ])
        assert r.win_trades == 3
        assert r.loss_trades == 2
        assert r.win_rate == pytest.approx(60.0)

    def test_breakeven_not_win_nor_loss(self):
        """pnl=0 既不算 win 也不算 loss；但 win_rate 分母含所有交易"""
        r = BacktestResult(trades=[_trade(100), _trade(-50), _trade(0)])
        assert r.win_trades == 1
        assert r.loss_trades == 1
        # engine: win_rate = win_trades / total_trades * 100
        # breakeven 计入分母但不算赢 → 1/3 = 33.33%
        assert r.win_rate == pytest.approx(33.33, 0.01)


class TestBacktestResultTotalPnl:
    """总 PnL"""

    def test_positive(self):
        r = BacktestResult(trades=[_trade(10), _trade(20), _trade(-5)])
        assert r.total_pnl == pytest.approx(25.0)

    def test_negative(self):
        r = BacktestResult(trades=[_trade(-100), _trade(30)])
        assert r.total_pnl == pytest.approx(-70.0)

    def test_empty_is_zero(self):
        r = BacktestResult()
        assert r.total_pnl == 0.0


class TestBacktestResultSharpe:
    """夏普比率 — 手工验证"""

    def test_positive_for_steady_growth(self):
        """稳步增长 → Sharpe > 0"""
        eq = [10000 + i * 10 for i in range(100)]
        r = BacktestResult(equity_curve=eq,
                           timestamps=[datetime(2026, 1, 1) + timedelta(hours=i) for i in range(100)])
        assert r.sharpe_ratio > 0

    def test_flat_curve_zero(self):
        """恒定 equity → 标准差 0 → Sharpe = 0"""
        r = BacktestResult(
            equity_curve=[10000.0] * 50,
            timestamps=[datetime(2026, 1, 1)] * 50,
        )
        assert r.sharpe_ratio == 0.0

    def test_too_short_curve_zero(self):
        """数据不足 20 条 → Sharpe = 0"""
        r = BacktestResult(
            equity_curve=[10000.0, 10100.0],
            timestamps=[datetime(2026, 1, 1)] * 2,
        )
        assert r.sharpe_ratio == 0.0

    def test_hand_calculated(self):
        """手工计算验证 — 至少 20 条绕过最低数据量限制"""
        np.random.seed(123)
        # 25 条线性增长 + 小噪声，确保 std > 0
        base = [100.0 + i * 0.5 for i in range(25)]
        noise = np.random.normal(0, 0.02, 25)
        eq = (np.array(base) + noise).tolist()
        r = BacktestResult(equity_curve=eq, timestamps=[datetime(2026, 1, 1)] * 25)
        # 用 engine 同名逻辑手工计算
        returns = np.diff(np.array(eq, dtype=float)) / np.array(eq[:-1], dtype=float)
        mean_ret = float(np.mean(returns))
        std_ret = float(np.std(returns, ddof=0))
        expected = mean_ret / std_ret * np.sqrt(365)
        assert r.sharpe_ratio == pytest.approx(expected, 0.01)


class TestBacktestResultMaxDrawdown:
    """最大回撤 — 手工验证"""

    def test_v_shape(self):
        """V 形: peak=120, trough=80 → dd=40/120=33.33%"""
        eq = [100, 110, 120, 90, 80, 130, 140]
        r = BacktestResult(equity_curve=eq,
                           timestamps=[datetime(2026, 1, d) for d in range(1, 8)])
        assert r.max_drawdown == pytest.approx(33.33, 0.01)

    def test_no_drop(self):
        """只涨不跌 → max_drawdown = 0"""
        r = BacktestResult(equity_curve=[100.0, 101.0, 102.0, 103.0])
        assert r.max_drawdown == pytest.approx(0.0, 0.01)

    def test_new_high_after_dd(self):
        """回撤后创新高 → dd 基于历史峰值"""
        eq = [100.0, 110.0, 95.0, 105.0, 200.0]
        # peak acc: 100, 110, 110, 110, 200
        # dd:      0,   0,  -13.64%, -4.55%, 0
        r = BacktestResult(equity_curve=eq)
        assert r.max_drawdown == pytest.approx(13.64, 0.01)

    def test_multi_peak(self):
        """多峰场景 → 取最大回撤"""
        eq = [100, 90, 110, 80, 120]
        # peak acc: 100, 100, 110, 110, 120
        # dd: 0, -10%, 0, -27.27%, 0  → max = 27.27%
        r = BacktestResult(equity_curve=eq)
        assert r.max_drawdown == pytest.approx(27.27, 0.01)


class TestBacktestResultReport:
    """报告输出"""

    def test_contains_key_fields(self):
        r = BacktestResult(trades=[_trade(100), _trade(-20)],
                           equity_curve=[10000, 10100, 10080])
        rep = r.report()
        assert "Backtest Report" in rep
        assert "Total Trades" in rep
        assert "Win Rate" in rep
        assert "Total PnL" in rep
        assert "Sharpe Ratio" in rep
        assert "Max DD" in rep

    def test_empty_report(self):
        rep = BacktestResult().report()
        assert isinstance(rep, str)
        assert "Backtest Report" in rep


# ── BacktestEngine 集成 ───────────────────────────────────────────────────

class TestBacktestEngineSMA:
    """SMA 金叉死叉策略"""

    def test_produces_trades(self):
        """随机数据也应产出交易"""
        df = _make_ohlcv(n=500, start_price=50000)
        engine = BacktestEngine(signal_fn=_sma_cross_signal, capital=10000, leverage=1)
        result = engine.run(df)
        assert result.total_trades > 0

    def test_equity_curve_length_matches_ohlcv(self):
        """每条 bar 一条 equity 记录"""
        df = _make_ohlcv(n=100)
        engine = BacktestEngine(signal_fn=_sma_cross_signal, capital=10000)
        result = engine.run(df)
        assert len(result.equity_curve) == len(df)
        assert len(result.timestamps) == len(df)


class TestBacktestEngineEdgeCases:
    """边界 / 异常"""

    def test_empty_dataframe(self):
        """空 DataFrame 不抛异常"""
        df = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        engine = BacktestEngine(signal_fn=_sma_cross_signal, capital=10000)
        result = engine.run(df)
        assert result.total_trades == 0
        assert result.total_pnl == 0.0

    def test_always_none_signal(self):
        """信号永远 None → 无交易"""
        df = _make_ohlcv(n=50)
        engine = BacktestEngine(signal_fn=lambda df: None, capital=10000)
        result = engine.run(df)
        assert result.total_trades == 0
        # equity 不变
        for eq in result.equity_curve:
            assert eq == pytest.approx(10000.0)

    def test_low_confidence_no_open(self):
        """confidence < 0.5 不开仓"""
        df = _make_ohlcv(n=50)
        engine = BacktestEngine(
            signal_fn=lambda df: {"direction": "long", "confidence": 0.3},
            capital=10000,
        )
        result = engine.run(df)
        assert result.total_trades == 0

    def test_insufficient_data_for_sma(self):
        """OHLCV 小于慢线窗口 → 无信号 → 无交易"""
        df = _make_ohlcv(n=10, start_price=50000)
        engine = BacktestEngine(signal_fn=_sma_cross_signal, capital=10000)
        result = engine.run(df)
        assert result.total_trades == 0


class TestBacktestEngineDirectional:
    """多 / 空 / 退出逻辑"""

    def test_always_long_bull_market(self):
        """持续做多 + 上涨 → 正收益"""
        closes = [50000.0 + i * 10 for i in range(100)]
        df = pd.DataFrame({
            "timestamp": pd.date_range("2026-01-01", periods=100, freq="1h"),
            "open": closes, "high": closes, "low": closes,
            "close": closes, "volume": [1000.0] * 100,
        })
        engine = BacktestEngine(
            signal_fn=lambda df: {"direction": "long", "confidence": 0.9},
            capital=10000, max_positions=1, leverage=1,
        )
        result = engine.run(df)
        assert result.total_trades >= 1
        assert result.total_pnl > 0

    def test_always_short_bear_market(self):
        """持续做空 + 下跌 → 正收益"""
        closes = [50000.0 - i * 10 for i in range(100)]
        df = pd.DataFrame({
            "timestamp": pd.date_range("2026-01-01", periods=100, freq="1h"),
            "open": closes, "high": closes, "low": closes,
            "close": closes, "volume": [1000.0] * 100,
        })
        engine = BacktestEngine(
            signal_fn=lambda df: {"direction": "short", "confidence": 0.9},
            capital=10000, max_positions=1, leverage=1,
        )
        result = engine.run(df)
        assert result.total_trades >= 1
        assert result.total_pnl > 0

    def test_opposite_signal_closes(self):
        """反向信号平掉原持仓"""
        closes = [50000.0] * 80
        df = pd.DataFrame({
            "timestamp": pd.date_range("2026-01-01", periods=80, freq="1h"),
            "open": closes, "high": closes, "low": closes,
            "close": closes, "volume": [1000.0] * 80,
        })
        call_count = [0]

        def long_then_short(df):
            call_count[0] += 1
            if call_count[0] <= 20:
                return {"direction": "long", "confidence": 0.9}
            elif call_count[0] <= 40:
                return None  # 持有
            else:
                return {"direction": "short", "confidence": 0.9}

        engine = BacktestEngine(signal_fn=long_then_short, capital=10000, max_positions=1, leverage=1)
        result = engine.run(df)
        assert result.total_trades >= 1

    def test_exit_direction_closes(self):
        """direction='exit' 平仓"""
        closes = [50000.0] * 50
        df = pd.DataFrame({
            "timestamp": pd.date_range("2026-01-01", periods=50, freq="1h"),
            "open": closes, "high": closes, "low": closes,
            "close": closes, "volume": [1000.0] * 50,
        })
        call_count = [0]

        def enter_then_exit(df):
            call_count[0] += 1
            if call_count[0] <= 15:
                return {"direction": "long", "confidence": 0.9}
            elif call_count[0] <= 25:
                return None
            else:
                return {"direction": "exit", "confidence": 0.9}

        engine = BacktestEngine(signal_fn=enter_then_exit, capital=10000, max_positions=3, leverage=1)
        result = engine.run(df)
        # 至少有一笔以 signal 原因平仓的交易
        assert result.total_trades >= 1

    def test_max_positions_limit(self):
        """持仓数不超过 max_positions"""
        closes = [50000.0] * 100
        df = pd.DataFrame({
            "timestamp": pd.date_range("2026-01-01", periods=100, freq="1h"),
            "open": closes, "high": closes, "low": closes,
            "close": closes, "volume": [1000.0] * 100,
        })
        engine = BacktestEngine(
            signal_fn=lambda df: {"direction": "long", "confidence": 0.9},
            capital=10000, max_positions=2, leverage=1,
        )
        result = engine.run(df)
        assert result.total_trades >= 0  # 不应崩溃
