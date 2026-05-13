"""
参数网格扫描优化脚本

用法:
    python -m vulpes_trader.scripts.optimize_params --symbol BTC/USDT:USDT
    python -m vulpes_trader.scripts.optimize_params --symbol ETH/USDT:USDT --rounds all
    python -m vulpes_trader.scripts.optimize_params --symbol SOL/USDT:USDT --rounds ema

输出优化报告到 reports/optimization/ 目录
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from vulpes_trader.backtest.optimizer import ParameterSweep

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("vulpes.scripts.optimize")


def build_signal_fn_for_params(ema_fast: List[int], ema_slow: List[int],
                               macd_fast: int, macd_slow: int, macd_signal: int):
    """构建可配置的信号函数"""
    def signal_fn(df):
        closes = df["close"].values
        if len(closes) < max(ema_slow[-1], 50):
            return {"direction": None, "confidence": 0.0}

        from vulpes_trader.signal.trend_follower import TrendFollower

        class MockK:
            def get_klines(self, s, t):
                return df

        trend = TrendFollower(MockK(), symbol="TEMP/USDT")
        # 用配置参数
        trend.ema_fast = ema_fast
        trend.ema_slow = ema_slow
        trend.macd_params = (macd_fast, macd_slow, macd_signal)

        fast_val = trend._ema(closes, ema_fast[0])[-1]
        slow_val = trend._ema(closes, ema_slow[0])[-1]
        if fast_val > slow_val:
            return {"direction": "long", "confidence": 0.6}
        return {"direction": "short", "confidence": 0.5}
    return signal_fn


def run_ema_round(symbol: str, data: pd.DataFrame, capital: float, full_scan: bool = False) -> List[Dict]:
    """第一轮: EMA/MACD 参数粗扫"""
    logger.info("=== 第一轮: EMA/MACD 粗扫 [%s] ===", symbol)

    if full_scan:
        param_grid = {
            "ema_fast_1": [5, 9, 12, 15, 20],
            "ema_fast_2": [8, 12, 15, 18],
            "ema_slow_1": [20, 26, 30, 40],
            "ema_slow_2": [30, 40, 50],
            "macd_fast": [8, 10, 12],
            "macd_slow": [20, 22, 26],
            "macd_signal": [6, 7, 9],
        }
    else:
        param_grid = {
            "ema_fast_1": [9, 12],
            "ema_fast_2": [12, 15],
            "ema_slow_1": [26, 30],
            "ema_slow_2": [40],
            "macd_fast": [12],
            "macd_slow": [26],
            "macd_signal": [9],
        }

    sweep = ParameterSweep(
        signal_fn=lambda df, **p: build_signal_fn_for_params(
            [p["ema_fast_1"], p["ema_fast_2"]],
            [p["ema_slow_1"], p["ema_slow_2"]],
            p["macd_fast"], p["macd_slow"], p["macd_signal"],
        )(df),
        param_grid=param_grid,
        engine_kwargs={"capital": capital},
    )
    top = sweep.run(data, top_n=10)

    results = []
    for pr in top:
        results.append({
            "params": pr.params,
            "trades": pr.result.total_trades,
            "win_rate": round(pr.result.win_rate, 2),
            "sharpe": round(pr.result.sharpe_ratio, 2),
            "max_dd": round(pr.result.max_drawdown, 4),
            "pnl": round(pr.result.total_pnl, 2),
            "score": round(pr.score, 4),
        })
    return results


def save_report(symbol: str, ema_results: List[Dict]):
    """保存优化报告"""
    report_dir = Path("reports") / "optimization"
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    report = {
        "symbol": symbol,
        "timestamp": timestamp,
        "ema_round": ema_results,
        "best_ema": ema_results[0] if ema_results else None,
    }
    safe_name = symbol.replace('/', '_').replace(':', '_')
    path = report_dir / f"{timestamp}_{safe_name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logger.info("报告已保存: %s", path)
    return path


def print_summary(results: List[Dict], title: str = "优化结果"):
    """打印结果摘要"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    print(f"{'排名':<4} {'参数':<30} {'胜率':<6} {'Sharpe':<8} {'回撤':<8} {'PnL':<10} {'Score':<8}")
    print(f"{'-'*74}")
    for i, r in enumerate(results[:5], 1):
        param_str = str(r["params"])
        print(f"{i:<4} {param_str:<30} {r['win_rate']:<6} {r['sharpe']:<8} "
              f"{r['max_dd']:<8} {r['pnl']:<10} {r['score']:<8}")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Vulpes Trader 参数优化")
    parser.add_argument("--symbol", default="BTC/USDT:USDT",
                        help="币种 (默认 BTC/USDT:USDT)")
    parser.add_argument("--rounds", choices=["ema", "all"],
                        default="ema", help="优化轮次 (默认 ema)")
    parser.add_argument("--capital", type=float, default=10000,
                        help="初始资金 (默认 10000)")
    parser.add_argument("--days", type=int, default=30,
                        help="历史数据天数 (默认 30)")
    parser.add_argument("--full", action="store_true",
                        help="全参数网格扫描 (默认精简测试网格)")
    args = parser.parse_args()

    # 使用本地 mock 数据用于测试
    logger.info("使用模拟数据 (参数 --fetch 使用真实数据)")
    import numpy as np
    np.random.seed(42)
    n = args.days * 288
    closes = 100 + np.cumsum(np.random.randn(n) * 0.5)
    data = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=n, freq="5min").astype(int) // 10**6,
        "open": closes * 0.995, "high": closes * 1.01,
        "low": closes * 0.99, "close": closes,
        "volume": np.random.rand(n) * 100,
    })

    ema_results = []

    # 第一轮: EMA/MACD
    if args.rounds in ("ema", "all"):
        ema_results = run_ema_round(args.symbol, data, args.capital, full_scan=args.full)
        if ema_results:
            print_summary(ema_results, f"{args.symbol} — EMA/MACD 参数扫描")

    # 保存报告
    path = save_report(args.symbol, ema_results)

    # 输出推荐配置
    if ema_results:
        best = ema_results[0]
        print("\n 推荐参数:")
        print(f"  ema_fast: [{best['params']['ema_fast_1']}, {best['params']['ema_fast_2']}]")
        print(f"  ema_slow: [{best['params']['ema_slow_1']}, {best['params']['ema_slow_2']}]")
        print(f"  macd:     [{best['params']['macd_fast']}, {best['params']['macd_slow']}, {best['params']['macd_signal']}]")
        print(f"  综合评分: {best['score']}")


if __name__ == "__main__":
    main()
