"""启动 Vulpes Trader Dashboard Demo 模式
PnL 数据全部从持仓推导，不生成独立随机数
"""
import sys
for k in list(sys.modules.keys()):
    if "vulpes_trader.dashboard" in k:
        del sys.modules[k]

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

import socket
def find_free_port(start=8770, end=8780):
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return 8781

PORT = find_free_port()
BASE_ASSETS = 100000.0


async def main():
    from vulpes_trader.dashboard.server import DashboardServer, _generate_demo_data

    dash = DashboardServer(port=PORT)
    demo_state = _generate_demo_data()
    dash.inject_state(demo_state)

    await dash.start()

    # PnL 历史曲线：从持仓推导
    pnl_history_points = []

    async def demo_loop():
        nonlocal pnl_history_points
        from random import uniform
        base_prices = {"BTC/USDT": 63820.0, "ETH/USDT": 3245.0, "SOL/USDT": 138.5}
        step = 0

        while True:
            await asyncio.sleep(3)
            step += 1

            # 更新持仓价格 & PnL
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

            # 今日盈亏 = 持仓 PnL 总和
            realtime_pnl = sum(p["pnl"] for p in dash._state.positions)
            dash._state.total_pnl = realtime_pnl
            total_assets = BASE_ASSETS + realtime_pnl
            daily_pct = (realtime_pnl / BASE_ASSETS) * 100

            dash._state.pnl_metrics = {
                "total_assets": round(total_assets, 2),
                "realtime": round(realtime_pnl, 2),
                "daily": round(realtime_pnl, 2),
                "daily_pct": round(daily_pct, 2),
                "monthly": round(realtime_pnl, 2),
                "monthly_pct": round(daily_pct, 2),
                "total": round(realtime_pnl, 2),
                "total_pct": round(daily_pct, 2),
            }

            # 曲线：记录每个步长的持仓 PnL
            pnl_history_points.append({"i": step, "value": round(realtime_pnl, 2)})
            if len(pnl_history_points) > 720:
                pnl_history_points = pnl_history_points[-720:]
            for r in ("1d", "7d", "30d", "180d", "360d"):
                dash._state.pnl_history[r] = pnl_history_points

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
            await dash.broadcast("pnl_update", {"metrics": dash._state.pnl_metrics})

    asyncio.create_task(demo_loop())
    print()
    print("[DEMO] Vulpes Trader Dashboard")
    print("=" * 40)
    print(">> http://127.0.0.1:%d" % PORT)
    print()

    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        await dash.stop()


if __name__ == "__main__":
    asyncio.run(main())
