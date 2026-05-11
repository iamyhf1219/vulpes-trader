"""回测参数扫描优化 — 网格搜索最优策略参数"""

import itertools
import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple, Any
import pandas as pd

from vulpes_trader.backtest.engine import BacktestEngine, BacktestResult

logger = logging.getLogger("vulpes.backtest.optimize")


@dataclass
class ParamResult:
    """单次参数组合的回测结果"""
    params: Dict[str, Any]
    result: BacktestResult

    @property
    def score(self) -> float:
        """综合评分: Sharpe * win_rate * sqrt(trades) / max_dd"""
        if self.result.total_trades < 3:
            return -999
        dd = max(self.result.max_drawdown, 1.0)
        return (
            max(self.result.sharpe_ratio, 0) *
            self.result.win_rate / 100 *
            (self.result.total_trades ** 0.3) / (dd ** 0.5)
        )


class ParameterSweep:
    """
    参数网格扫描

    用法:
        def my_strategy(df, fast=5, slow=20):
            ...

        sweep = ParameterSweep(
            signal_fn=my_strategy,
            param_grid={"fast": [3,5,10], "slow": [20,50]},
            engine_kwargs={"capital": 10000},
        )
        results = sweep.run(ohlcv)
        best = results[0]
        print(best.params, best.result.sharpe_ratio)
    """

    def __init__(
        self,
        signal_fn: Callable,
        param_grid: Dict[str, List],
        engine_kwargs: Optional[Dict] = None,
        multi_data: bool = False,
    ):
        self.signal_fn = signal_fn
        self.param_grid = param_grid
        self.engine_kwargs = engine_kwargs or {}
        self.multi_data = multi_data  # True if data is Dict[str, DataFrame]

    def run(
        self,
        data: Any,
        top_n: int = 5,
        progress: bool = True,
    ) -> List[ParamResult]:
        """执行全网格扫描"""
        keys = list(self.param_grid.keys())
        combos = list(itertools.product(*self.param_grid.values()))

        results: List[ParamResult] = []
        for i, combo in enumerate(combos):
            params = dict(zip(keys, combo))

            # 包装信号函数绑定参数
            def make_signal(p):
                return lambda df, p=p: self.signal_fn(df, **p)

            engine = BacktestEngine(
                signal_fn=make_signal(params),
                **self.engine_kwargs,
            )

            result = engine.run_multi(data) if self.multi_data else engine.run(data)
            final = result if isinstance(result, BacktestResult) else result.get("summary", result)

            results.append(ParamResult(params=params, result=final))

            if progress:
                score_str = f"{final.total_pnl:+.1f}" if final.total_trades > 0 else "skip"
                logger.info("  [%d/%d] %s → trades=%d sharpe=%.2f dd=%.1f%% pnl=%s",
                            i + 1, len(combos), params,
                            final.total_trades, final.sharpe_ratio,
                            final.max_drawdown, score_str)

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_n]

    def run_parallel(
        self,
        data: Any,
        top_n: int = 5,
        max_workers: int = 4,
    ) -> List[ParamResult]:
        """并行网格扫描"""
        import concurrent.futures
        keys = list(self.param_grid.keys())
        combos = list(itertools.product(*self.param_grid.values()))

        def _eval(combo):
            params = dict(zip(keys, combo))
            engine = BacktestEngine(
                signal_fn=lambda df, p=params: self.signal_fn(df, **p),
                **self.engine_kwargs,
            )
            result = engine.run_multi(data) if self.multi_data else engine.run(data)
            final = result if isinstance(result, BacktestResult) else result.get("summary", result)
            return ParamResult(params=params, result=final)

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            for pr in ex.map(_eval, combos):
                results.append(pr)
                logger.info("  %s → trades=%d sharpe=%.2f", pr.params, pr.result.total_trades, pr.result.sharpe_ratio)

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_n]
