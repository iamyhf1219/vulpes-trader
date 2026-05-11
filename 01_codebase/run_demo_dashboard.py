"""启动 Vulpes Trader Dashboard Demo 模式
PnL 收益面板与持仓数据动态联动
"""
import sys
for k in list(sys.modules.keys()):
    if "vulpes_trader.dashboard" in k:
        del sys.modules[k]

import asyncio
import logging
from copy import deepcopy

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

PORT = 8771
BASE_ASSETS = 100000.0  # 初始本金


async def main():
    from vulpes_trader.dashboard.server import DashboardServer, _generate_demo_data

    dash = DashboardServer(port=PORT)
    demo_state = _generate_demo_data()
    dash.inject_state(demo_state)

    await dash.start()

    # 初始化 PnL 累计跟踪
    cumulative_pnl = demo_state.total_pnl  # 552.4
    daily_start_pnl = cumulative_pnl       # 今日起始
    pnl_history_30d = list(demo_state.pnl_history.get("30d", []))  # 已有360点

    async def demo_loop():
        from random import uniform
        nonlocal cumulative_pnl, daily_start_pnl, pnl_history_30d

        base_prices = {"BTC/USDT": 63820.0, "ETH/USDT": 3245.0, "SOL/USDT": 138.5}
        step_count = 0

        while True:
            await asyncio.sleep(3)
            step_count += 1

            # ---- 1. 更新持仓价格 ----
            for pos in dash._state.positions:
                sym = pos["symbol"]
                bp = base_prices.get(sym, 100.0)
                change = bp * uniform(-0.002, 0.002)
                bp += change
                base_prices[sym] = bp
                pos["current_price"] = round(bp, 2)
                side_mult = 1 if pos["side"] == "long" else -1
                pos["pnl"] = round((bp - pos["entry_price"]) * pos["quantity"] * side_mult, 2)
                pos["pnl_pct"] = round(((bp - pos["entry_price"]) / pos["entry_price"]) * 100, 2)

            # ---- 2. 计算实时 PnL ----
            realtime_pnl = sum(p["pnl"] for p in dash._state.positions)
            dash._state.total_pnl = realtime_pnl

            # 模拟累计 PnL 缓慢增长（加入随机偏移）
            cumulative_pnl += uniform(-2, 8)
            daily_pnl = cumulative_pnl - daily_start_pnl

            # ---- 3. 更新 PnL 指标（与持仓联动） ----
            total_assets = BASE_ASSETS + cumulative_pnl
            daily_pct = (daily_pnl / max(BASE_ASSETS + daily_start_pnl, 1)) * 100

            dash._state.pnl_metrics = {
                "total_assets": round(total_assets, 2),
                "realtime": round(realtime_pnl, 2),
                "daily": round(daily_pnl, 2),
                "daily_pct": round(daily_pct, 2),
                "monthly": round(cumulative_pnl, 2),
                "monthly_pct": round((cumulative_pnl / BASE_ASSETS) * 100, 2),
                "total": round(cumulative_pnl, 2),
                "total_pct": round((cumulative_pnl / BASE_ASSETS) * 100, 2),
            }

            # ---- 4. 扩展 PnL 历史曲线 ----
            pnl_history_30d.append({
                "i": len(pnl_history_30d),
                "value": round(cumulative_pnl + uniform(-5, 5), 2)
            })
            # 保持最多 720 点
            if len(pnl_history_30d) > 720:
                pnl_history_30d = pnl_history_30d[-720:]
            dash._state.pnl_history["30d"] = pnl_history_30d

            # ---- 5. 广播所有更新 ----
            await dash.broadcast("positions", dash._state.positions)
            await dash.broadcast("status", {
                "total_pnl": round(realtime_pnl, 2),
                "active_positions": len(dash._state.positions),
            })
            await dash.broadcast("performance", {
                "total_pnl": round(realtime_pnl, 2),
                "win_rate": dash._state.win_rate,
                "trade_count": dash._state.trade_count,
                "daily_loss": dash._state.daily_loss,
            })
            await dash.broadcast("pnl_update", {
                "metrics": dash._state.pnl_metrics,
            })

            # 模拟每60步重置今日起始（模拟新的一天）
            if step_count % 60 == 0:
                daily_start_pnl = cumulative_pnl

    asyncio.create_task(demo_loop())
    print()
    print("[DEMO] Vulpes Trader Dashboard")
    print("=" * 40)
    print(">> http://127.0.0.1:%d" % PORT)
    print(">> 3秒自动更新, PnL 与持仓实时联动")
    print()

    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        await dash.stop()


if __name__ == "__main__":
    asyncio.run(main())
