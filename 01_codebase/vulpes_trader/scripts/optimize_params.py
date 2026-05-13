"""
参数网格扫描优化脚本 — 快速版（专用趋势回测器）

用法:
    # 快速扫描（7天模拟数据）
    python -m vulpes_trader.scripts.optimize_params --symbol BTC/USDT:USDT
    
    # 全网格扫描
    python -m vulpes_trader.scripts.optimize_params --symbol BTC/USDT:USDT --full
    
    # 真实数据全量
    python -m vulpes_trader.scripts.optimize_params --symbol SOL/USDT:USDT --fetch --long

输出优化报告到 reports/optimization/ 目录
"""

import argparse
import json
import logging
import sys
import itertools
import concurrent.futures
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable, Tuple

import pandas as pd
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("vulpes.scripts.optimize")

# --- 预计算 EMA ---

def ema_full(closes: np.ndarray, period: int) -> np.ndarray:
    """一次性预计算完整序列 EMA"""
    n = len(closes)
    result = np.full(n, np.nan)
    if n < period:
        return result
    result[period - 1] = np.mean(closes[:period])
    m = 2 / (period + 1)
    for i in range(period, n):
        result[i] = (closes[i] - result[i - 1]) * m + result[i - 1]
    return result


# --- 快速趋势回测（单次扫描，无需 BacktestEngine）---

def fast_trend_backtest(closes: np.ndarray, ema_fast: List[int], ema_slow: List[int],
                         capital: float = 10000, leverage: int = 5) -> dict:
    """
    快速趋势回测 — 一次性扫描所有 K 线
    
    返回: dict with trades, pnl, sharpe, win_rate, max_dd
    """
    n = len(closes)
    slow_max = max(ema_slow[-1], 50)
    if n < slow_max + 5:
        return {"trades": 0, "pnl": 0.0, "sharpe": 0.0, "win_rate": 0.0, 
                "max_dd": 0.0, "score": -999}

    # 预计算所有 EMA
    e1 = ema_full(closes, ema_fast[0])
    e2 = ema_full(closes, ema_fast[1] if len(ema_fast) > 1 else ema_fast[0])
    s1 = ema_full(closes, ema_slow[0])
    s2 = ema_full(closes, ema_slow[1] if len(ema_slow) > 1 else ema_slow[0])

    # 逐 K 线模拟
    trades = []
    in_position = False
    position_side = None
    entry_price = 0.0
    entry_idx = 0
    qty = 0.0
    equity_curve = []

    for i in range(slow_max, n):
        if np.isnan(e1[i]) or np.isnan(e2[i]) or np.isnan(s1[i]) or np.isnan(s2[i]):
            continue
        if i < 1 or np.isnan(e1[i-1]) or np.isnan(e2[i-1]):
            continue

        price = closes[i]
        equity = capital

        # 现有持仓浮动 PnL
        if in_position:
            if position_side == "long":
                pnl = (price - entry_price) * qty * leverage
            else:
                pnl = (entry_price - price) * qty * leverage
            equity = capital + pnl

        # 信号计算
        ef1, ef1p = e1[i], e1[i-1]
        ef2, ef2p = e2[i], e2[i-1]
        es1, es1p = s1[i], s1[i-1]
        es2, es2p = s2[i], s2[i-1]

        trend_up = es1 > es2
        trend_down = es1 < es2
        fast_cross_up = ef1p <= ef2p and ef1 > ef2
        fast_cross_down = ef1p >= ef2p and ef1 < ef2

        # 平仓信号
        if in_position:
            should_exit = False
            exit_reason = ""
            if position_side == "long" and (trend_up and fast_cross_down):
                should_exit = True
                exit_reason = "trend_exhaustion_long"
            elif position_side == "short" and (trend_down and fast_cross_up):
                should_exit = True
                exit_reason = "trend_exhaustion_short"

            if should_exit:
                pnl = (price - entry_price) * qty * leverage if position_side == "long" else \
                      (entry_price - price) * qty * leverage
                pnl_pct = pnl / (entry_price * qty) * 100 if entry_price * qty > 0 else 0
                trades.append({
                    "side": position_side, "entry": entry_price, "exit": price,
                    "pnl": pnl, "pnl_pct": pnl_pct, "reason": exit_reason,
                })
                in_position = False
                capital = equity

        # 开仓信号
        if not in_position:
            if fast_cross_up and trend_up:
                pos_value = capital * 0.3 / max(leverage, 1)
                qty = pos_value / price
                in_position = True
                position_side = "long"
                entry_price = price
                entry_idx = i
            elif fast_cross_down and trend_down:
                pos_value = capital * 0.3 / max(leverage, 1)
                qty = pos_value / price
                in_position = True
                position_side = "short"
                entry_price = price
                entry_idx = i

        equity_curve.append(equity)

    # 平掉尾仓
    if in_position and n > 0:
        price = closes[-1]
        pnl = (price - entry_price) * qty * leverage if position_side == "long" else \
              (entry_price - price) * qty * leverage
        pnl_pct = pnl / (entry_price * qty) * 100 if entry_price * qty > 0 else 0
        trades.append({
            "side": position_side, "entry": entry_price, "exit": price,
            "pnl": pnl, "pnl_pct": pnl_pct, "reason": "end",
        })

    # 计算指标
    n_trades = len(trades)
    if n_trades < 3:
        return {"trades": n_trades, "pnl": 0.0, "sharpe": 0.0, "win_rate": 0.0,
                "max_dd": 0.0, "score": -999}

    pnls = np.array([t["pnl"] for t in trades])
    wins = np.sum(pnls > 0)
    total_pnl = float(np.sum(pnls))
    win_rate = float(wins / n_trades * 100)

    # Sharpe
    eq = np.array(equity_curve)
    if len(eq) > 20:
        rets = np.diff(eq) / eq[:-1]
        rets = rets[~np.isnan(rets)]
        sharpe = float(np.mean(rets) / max(np.std(rets), 1e-10) * np.sqrt(365)) if len(rets) > 0 else 0.0
    else:
        sharpe = 0.0

    # Max DD
    if len(eq) > 0:
        peak = np.maximum.accumulate(eq)
        dd = (eq - peak) / np.maximum(peak, 1)
        max_dd = float(abs(np.min(dd)) * 100)
    else:
        max_dd = 0.0

    # Score = sharpe * win_rate * sqrt(trades) / sqrt(max_dd)
    score = max(sharpe, 0) * win_rate / 100 * (n_trades ** 0.3) / max(max_dd, 1.0) ** 0.5

    return {
        "trades": n_trades, "pnl": round(total_pnl, 2),
        "sharpe": round(sharpe, 4), "win_rate": round(win_rate, 2),
        "max_dd": round(max_dd, 4), "score": round(score, 4),
    }


# --- 参数网格扫描 ---

def run_scan(data: pd.DataFrame, capital: float, full_scan: bool = False,
             parallel: int = 0) -> List[Dict]:
    """执行参数网格扫描"""
    closes = data["close"].values.astype(float)

    if full_scan:
        param_space = {
            "f1": [3, 5, 7, 9, 12, 15, 20],
            "f2": [5, 8, 10, 12, 15, 18],
            "s1": [15, 20, 26, 30, 35, 40, 50],
            "s2": [20, 26, 30, 40, 50, 55],
        }
    else:
        param_space = {
            "f1": [5, 7, 9, 12, 15],
            "f2": [8, 10, 12, 15],
            "s1": [20, 26, 30, 40],
            "s2": [30, 40, 50],
        }

    keys = list(param_space.keys())
    combos = list(itertools.product(*param_space.values()))
    total = len(combos)
    logger.info("参数网格: %d 种组合", total)

    def eval_one(combo):
        params = dict(zip(keys, combo))
        ema_fast = [params["f1"], params["f2"]]
        ema_slow = [params["s1"], params["s2"]]
        result = fast_trend_backtest(closes, ema_fast, ema_slow, capital)
        result["params"] = {"ema_fast": ema_fast, "ema_slow": ema_slow}
        return result

    results = []
    if parallel > 0:
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as ex:
            for r in ex.map(eval_one, combos):
                if r["trades"] >= 3:
                    results.append(r)
                if len(results) % 20 == 0 and len(results) > 0:
                    logger.info("  已完成 %d/%d...", len(results), total)
    else:
        for i, combo in enumerate(combos):
            r = eval_one(combo)
            if r["trades"] >= 3:
                results.append(r)
            if (i + 1) % 20 == 0:
                logger.info("  [%d/%d]...", i + 1, total)
            elif total <= 50:
                logger.info("  [%d/%d] %s → trades=%d sharpe=%.2f pnl=%s",
                            i + 1, total, r["params"], r["trades"], r["sharpe"], r.get("pnl", "0"))

    # 按 score 排序
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:10]


def save_report(symbol: str, results: List[Dict]) -> str:
    """保存优化报告"""
    report_dir = Path("reports") / "optimization"
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    report = {
        "symbol": symbol,
        "timestamp": timestamp,
        "results": results,
        "best": results[0] if results else None,
    }
    safe_name = symbol.replace('/', '_').replace(':', '_')
    path = report_dir / f"{timestamp}_{safe_name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logger.info("报告已保存: %s", path)
    return path


def print_table(results: List[Dict], title: str = "优化结果"):
    """打印结果"""
    print(f"\n{'='*85}")
    print(f"  {title}")
    print(f"{'='*85}")
    h = f"{'排名':<4} {'EMA快':<14} {'EMA慢':<14} {'交易数':<6} {'胜率':<6} {'Sharpe':<8} {'回撤':<8} {'PnL':<10} {'Score':<8}"
    print(h)
    print('-' * 85)
    for i, r in enumerate(results[:8], 1):
        ema_f = str(r["params"]["ema_fast"])
        ema_s = str(r["params"]["ema_slow"])
        print(f"{i:<4} {ema_f:<14} {ema_s:<14} {r['trades']:<6} {r['win_rate']:<6} "
              f"{r['sharpe']:<8} {r['max_dd']:<8} {r['pnl']:<10} {r['score']:<8}")
    print('=' * 85)


def generate_mock_data(days: int = 7) -> pd.DataFrame:
    """生成带趋势的模拟行情数据"""
    np.random.seed(42)
    n = days * 288
    trend = np.linspace(0, 5, n)
    closes = 50000 + trend + np.cumsum(np.random.randn(n) * 100)
    closes = np.maximum(closes, 40000)
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=n, freq="5min").astype(int) // 10**6,
        "open": closes * 0.995, "high": closes * 1.015,
        "low": closes * 0.985, "close": closes,
        "volume": np.random.rand(n) * 100,
    })


def fetch_real_data(symbol: str, days: int = 7) -> pd.DataFrame:
    """从 Binance 拉取真实 K 线（公共 API，无需 Key）"""
    import requests

    logger.info("拉取 %s 历史数据 (%d 天, 5m)...", symbol, days)
    limit = days * 288
    spot_symbol = symbol.replace("/USDT:USDT", "USDT")

    try:
        url = f"https://api.binance.com/api/v3/klines"
        params = {"symbol": spot_symbol, "interval": "5m", "limit": limit}
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        df = pd.DataFrame(data, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_vol", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore"
        ])
        df = df[["timestamp", "open", "high", "low", "close", "volume"]]
        for c in ["open", "high", "low", "close", "volume"]:
            df[c] = df[c].astype(float)
        df["timestamp"] = df["timestamp"].astype(int) // 10**6
        logger.info("获取到 %d 条 K 线", len(df))
        return df
    except Exception as e:
        logger.error("获取数据失败: %s", e)
        logger.info("回退到模拟数据")
        return generate_mock_data(days)


def main():
    parser = argparse.ArgumentParser(description="Vulpes Trader 参数优化")
    parser.add_argument("--symbol", default="BTC/USDT:USDT", help="币种")
    parser.add_argument("--capital", type=float, default=10000, help="初始资金")
    parser.add_argument("--days", type=int, default=7, help="数据天数 (默认7)")
    parser.add_argument("--full", action="store_true", help="全网格扫描")
    parser.add_argument("--long", action="store_true", help="30天完整数据")
    parser.add_argument("--parallel", type=int, default=0, help="并行 worker 数")
    parser.add_argument("--fetch", action="store_true", help="拉取实时数据")
    args = parser.parse_args()

    days = 30 if args.long else args.days

    if args.fetch:
        data = fetch_real_data(args.symbol, days)
    else:
        data = generate_mock_data(days)
        logger.info("使用模拟数据（用 --fetch 拉取真实数据）")

    logger.info("=== EMA 参数扫描 [%s] (%d天, %d条K线) ===",
                args.symbol, days, len(data))

    results = run_scan(data, args.capital, full_scan=args.full, parallel=args.parallel)

    if results:
        print_table(results, f"{args.symbol} — 参数扫描")

    path = save_report(args.symbol, results)

    if results:
        best = results[0]
        p = best["params"]
        print(f"\n>> 推荐参数 [{args.symbol}]:")
        print(f"  ema_fast: {p['ema_fast']}   ema_slow: {p['ema_slow']}")
        print(f"  交易数: {best['trades']}   胜率: {best['win_rate']}%   "
              f"Sharpe: {best['sharpe']}   回撤: {best['max_dd']}%   "
              f"PnL: {best['pnl']}  评分: {best['score']}")
        print(f"\n  报告: {path}")


if __name__ == "__main__":
    main()
