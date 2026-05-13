"""多币种并行回测 — 同时评估多币种参数表现"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
import pandas as pd
import numpy as np

from vulpes_trader.backtest.engine import BacktestEngine, BacktestResult

logger = logging.getLogger("vulpes.backtest.multisymbol")


@dataclass
class SymbolResult:
    """单个币种的回测结果"""
    symbol: str
    trades: int
    win_rate: float
    sharpe: float
    max_dd: float
    total_pnl: float
    score: float
    details: BacktestResult


@dataclass
class CombinedResult:
    """多币种综合回测结果"""
    symbol_results: Dict[str, SymbolResult]
    combined_score: float
    total_trades: int

    def summary(self) -> Dict:
        return {
            "combined_score": round(self.combined_score, 4),
            "total_trades": self.total_trades,
            "symbols": {
                sym: {
                    "trades": r.trades,
                    "win_rate": round(r.win_rate, 2),
                    "sharpe": round(r.sharpe, 2),
                    "max_dd": round(r.max_dd, 4),
                    "pnl": round(r.total_pnl, 2),
                    "score": round(r.score, 4),
                }
                for sym, r in self.symbol_results.items()
            },
        }


def compute_score(result: BacktestResult) -> float:
    """综合评分: sharpe * win_rate * sqrt(trades) / sqrt(max_dd)"""
    if result.total_trades < 3:
        return -999
    dd = max(result.max_drawdown, 1.0)
    return (
        max(result.sharpe_ratio, 0) *
        result.win_rate / 100 *
        (result.total_trades ** 0.3) / (dd ** 0.5)
    )


class MultiSymbolBacktest:
    """多币种回测运行器

    同时跑 N 个币种的回测并输出综合评分
    """

    def __init__(
        self,
        signal_fn_builder: Callable[[str], Callable],
        engine_kwargs: Optional[Dict] = None,
        score_fn: Callable = compute_score,
        min_trades: int = 10,
    ):
        self.signal_fn_builder = signal_fn_builder
        self.engine_kwargs = engine_kwargs or {}
        self.score_fn = score_fn
        self.min_trades = min_trades

    def run(
        self, symbol_data: Dict[str, pd.DataFrame]
    ) -> CombinedResult:
        """运行多币种回测

        Args:
            symbol_data: {symbol: OHLCV DataFrame}

        Returns:
            CombinedResult 综合结果
        """
        symbol_results = {}
        total_trades = 0

        for symbol, df in symbol_data.items():
            signal_fn = self.signal_fn_builder(symbol)
            engine = BacktestEngine(
                signal_fn=signal_fn,
                **self.engine_kwargs,
            )
            result = engine.run(df)
            score = self.score_fn(result)

            sr = SymbolResult(
                symbol=symbol,
                trades=result.total_trades,
                win_rate=result.win_rate,
                sharpe=result.sharpe_ratio,
                max_dd=result.max_drawdown,
                total_pnl=result.total_pnl,
                score=score,
                details=result,
            )
            symbol_results[symbol] = sr
            total_trades += result.total_trades
            logger.info(
                "  %s: trades=%d sharpe=%.2f dd=%.1f%% pnl=%.1f score=%.2f",
                symbol, result.total_trades, result.sharpe_ratio,
                result.max_drawdown, result.total_pnl, score,
            )

        # 综合评分: 各币种评分的（几何+惩罚）平均
        scores = [sr.score for sr in symbol_results.values() if sr.trades >= self.min_trades]
        if not scores:
            combined = -999
        else:
            avg = np.mean(scores)
            # 惩罚: 交易次数不足的币种数量
            penalty = sum(1 for sr in symbol_results.values() if sr.trades < self.min_trades)
            combined = avg * (0.9 ** penalty)

        return CombinedResult(
            symbol_results=symbol_results,
            combined_score=combined,
            total_trades=total_trades,
        )

    async def run_parallel(
        self, symbol_data: Dict[str, pd.DataFrame], max_concurrent: int = 3
    ) -> CombinedResult:
        """异步并行运行多币种回测"""
        sem = asyncio.Semaphore(max_concurrent)

        async def _run_one(symbol: str, df: pd.DataFrame) -> SymbolResult:
            async with sem:
                signal_fn = self.signal_fn_builder(symbol)
                engine = BacktestEngine(
                    signal_fn=signal_fn,
                    **self.engine_kwargs,
                )
                result = await asyncio.to_thread(engine.run, df)
                score = self.score_fn(result)
                return SymbolResult(
                    symbol=symbol, trades=result.total_trades,
                    win_rate=result.win_rate, sharpe=result.sharpe_ratio,
                    max_dd=result.max_drawdown, total_pnl=result.total_pnl,
                    score=score, details=result,
                )

        tasks = [_run_one(sym, df) for sym, df in symbol_data.items()]
        results = await asyncio.gather(*tasks)

        symbol_results = {r.symbol: r for r in results}
        total_trades = sum(r.trades for r in results)

        scores = [r.score for r in results if r.trades >= self.min_trades]
        combined = np.mean(scores) * (0.9 ** sum(1 for r in results if r.trades < self.min_trades)) if scores else -999

        return CombinedResult(
            symbol_results=symbol_results,
            combined_score=combined,
            total_trades=total_trades,
        )
