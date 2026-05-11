"""回测引擎 — 用历史数据驱动交易流水线模拟"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Callable
import pandas as pd
import numpy as np

logger = logging.getLogger("vulpes.backtest")


@dataclass
class BacktestTrade:
    """模拟交易记录"""
    symbol: str
    side: str
    entry_time: datetime
    exit_time: Optional[datetime] = None
    entry_price: float = 0.0
    exit_price: Optional[float] = None
    quantity: float = 0.0
    leverage: int = 1
    pnl: float = 0.0
    pnl_pct: float = 0.0
    exit_reason: str = ""


@dataclass
class BacktestResult:
    """回测结果"""
    trades: List[BacktestTrade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    timestamps: List[datetime] = field(default_factory=list)

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def win_trades(self) -> int:
        return sum(1 for t in self.trades if t.pnl > 0)

    @property
    def loss_trades(self) -> int:
        return sum(1 for t in self.trades if t.pnl < 0)

    @property
    def win_rate(self) -> float:
        return self.win_trades / max(self.total_trades, 1) * 100

    @property
    def total_pnl(self) -> float:
        return sum(t.pnl for t in self.trades)

    @property
    def sharpe_ratio(self) -> float:
        if len(self.equity_curve) < 20:
            return 0.0
        returns = np.diff(self.equity_curve) / np.array(self.equity_curve[:-1])
        if len(returns) == 0 or np.std(returns) == 0:
            return 0.0
        return float(np.mean(returns) / np.std(returns) * np.sqrt(365))

    @property
    def max_drawdown(self) -> float:
        if not self.equity_curve:
            return 0.0
        peak = np.maximum.accumulate(self.equity_curve)
        dd = (self.equity_curve - peak) / peak
        return float(abs(min(dd)) * 100) if len(dd) > 0 else 0.0

    def report(self) -> str:
        lines = [
            "=" * 50,
            "  Backtest Report",
            "=" * 50,
            f"  Total Trades:  {self.total_trades}",
            f"  Win Rate:      {self.win_rate:.1f}%  ({self.win_trades}W / {self.loss_trades}L)",
            f"  Total PnL:     {self.total_pnl:+.2f}",
            f"  Sharpe Ratio:  {self.sharpe_ratio:.2f}",
            f"  Max DD:        {self.max_drawdown:.2f}%",
            f"  Best Trade:    {max((t.pnl for t in self.trades), default=0):+.2f}",
            f"  Worst Trade:   {min((t.pnl for t in self.trades), default=0):+.2f}",
            f"  Avg PnL/Trade: {(self.total_pnl / max(self.total_trades,1)):.2f}",
        ]
        return "\n".join(lines)


class BacktestEngine:
    """
    回测引擎

    用法:
        engine = BacktestEngine(
            signal_fn=my_signal_generator,
            capital=10000.0,
        )
        result = engine.run(ohlcv_data)
        print(result.report())
    """

    def __init__(
        self,
        signal_fn: Callable,
        capital: float = 10000.0,
        max_positions: int = 3,
        leverage: int = 5,
    ):
        self.signal_fn = signal_fn
        self.capital = capital
        self.max_positions = max_positions
        self.leverage = leverage

    def run_multi(self, data: Dict[str, pd.DataFrame]) -> Dict[str, BacktestResult]:
        """
        多币种并行回测

        Args:
            data: {symbol: DataFrame} 每个币种的 OHLCV 数据

        Returns:
            {symbol: BacktestResult} 每个币种的回测结果
        """
        # 对齐时间轴
        aligned = {}
        for sym, df in data.items():
            d = df.copy().sort_values("timestamp")
            d["_ts"] = pd.to_datetime(d["timestamp"])
            aligned[sym] = d.set_index("_ts")

        if not aligned:
            return {}

        # 共用时间轴
        all_times = pd.DatetimeIndex([])
        for d in aligned.values():
            all_times = all_times.union(d.index)
        all_times = all_times.sort_values()

        # 每个币种独立运行回测
        results: Dict[str, BacktestResult] = {}
        for sym, df in aligned.items():
            results[sym] = self.run(df.drop(columns=["timestamp"], errors="ignore").reset_index().rename(columns={"_ts": "timestamp"}))

        # 组合权益曲线：按时间相加
        portfolio_equity = pd.Series(dtype=float)
        for sym, r in results.items():
            eq = pd.Series(r.equity_curve, index=r.timestamps)
            portfolio_equity = portfolio_equity.add(eq, fill_value=self.capital)

        # 汇总结果
        all_trades = []
        for sym, r in results.items():
            all_trades.extend(r.trades)

        summary = BacktestResult(
            trades=all_trades,
            equity_curve=portfolio_equity.values.tolist(),
            timestamps=portfolio_equity.index.tolist(),
        )
        return {"summary": summary, "details": results}

    def run(self, ohlcv: pd.DataFrame) -> BacktestResult:
        """
        单币种回测

        Args:
            ohlcv: DataFrame 必须包含 ['timestamp','open','high','low','close','volume']

        Returns:
            BacktestResult
        """
        result = BacktestResult()
        positions: Dict[str, dict] = {}
        equity = self.capital

        ohlcv = ohlcv.sort_values("timestamp").reset_index(drop=True)

        for i in range(len(ohlcv)):
            row = ohlcv.iloc[i]
            ts = pd.to_datetime(row["timestamp"])
            price = float(row["close"])
            symbol = "BACKTEST"  # 单币种简化

            # 更新持仓浮动 PnL
            for sym, pos in list(positions.items()):
                pos["current_price"] = price
                if pos["side"] == "long":
                    pos["pnl"] = (price - pos["entry_price"]) * pos["quantity"] * pos["leverage"]
                else:
                    pos["pnl"] = (pos["entry_price"] - price) * pos["quantity"] * pos["leverage"]

            # 生成信号
            signal = self.signal_fn(ohlcv.iloc[:i+1])
            equity = self.capital + sum(p["pnl"] for p in positions.values())
            result.equity_curve.append(equity)
            result.timestamps.append(ts)

            if signal is None:
                continue

            direction = signal.get("direction")
            confidence = signal.get("confidence", 0.5)

            if confidence < 0.5:
                continue

            # 平仓逻辑
            for sym, pos in list(positions.items()):
                exit_signal = (
                    (direction == "exit" and confidence > 0.5) or
                    (direction == "short" and pos["side"] == "long") or
                    (direction == "long" and pos["side"] == "short")
                )
                if not exit_signal:
                    continue

                pnl = pos["pnl"]
                result.trades.append(BacktestTrade(
                    symbol=sym, side=pos["side"],
                    entry_time=pos["entry_time"], exit_time=ts,
                    entry_price=pos["entry_price"], exit_price=price,
                    quantity=pos["quantity"], leverage=pos["leverage"],
                    pnl=pnl, pnl_pct=pnl / max(pos["entry_value"], 1) * 100,
                    exit_reason="signal",
                ))
                equity += pnl
                del positions[sym]
                logger.debug("BT close %s %s pnl=%.2f", sym, pos["side"], pnl)

            # 开仓逻辑
            if direction in ("long", "short") and len(positions) < self.max_positions:
                pos_value = equity * 0.3 / max(self.leverage, 1)
                qty = pos_value / price
                pos_key = f"{symbol}_{direction}_{i}"
                positions[pos_key] = {
                    "symbol": symbol, "side": direction,
                    "entry_price": price, "quantity": qty,
                    "leverage": self.leverage, "entry_value": pos_value,
                    "entry_time": ts, "pnl": 0.0,
                }
                logger.debug("BT open %s %s @%.2f qty=%.4f", symbol, direction, price, qty)

        # 平掉剩余持仓
        for sym, pos in list(positions.items()):
            price = float(ohlcv.iloc[-1]["close"])
            pnl = pos["pnl"]
            result.trades.append(BacktestTrade(
                symbol=sym, side=pos["side"],
                entry_time=pos["entry_time"], exit_time=pd.to_datetime(ohlcv.iloc[-1]["timestamp"]),
                entry_price=pos["entry_price"], exit_price=price,
                quantity=pos["quantity"], leverage=pos["leverage"],
                pnl=pnl, pnl_pct=pnl / max(pos["entry_value"], 1) * 100,
                exit_reason="end_of_data",
            ))

        return result
