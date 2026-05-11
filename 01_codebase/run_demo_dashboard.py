"""启动 Vulpes Trader Dashboard Demo 模式
PnL 收益面板与持仓数据动态联动
"""
import sys
for k in list(sys.modules.keys()):
    if "vulpes_trader.dashboard" in k:
        del sys.modules[k]

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# 尝试一个确保可用的端口
import socket
def find_free_port(start=8770, end=8780):
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return 8781  # fallback

PORT = find_free_port()


async def main():
    from vulpes_trader.dashboard.server import DashboardServer, _generate_demo_data

    dash = DashboardServer(port=PORT)
    demo_state = _generate_demo_data()
    dash.inject_state(demo_state)

    await dash.start()

    # 初始化 PnL 累计跟踪
    cumulative_pnl = demo_state.total_pnl
    daily_start_pnl = cumulative_pnl
    pnl_history_30d = list(demo_state.pnl_history.get("30d", []))

    async def demo_loop():
        from random import uniform
        nonlocal cumulative_pnl, daily_start_pnl, pnl_history_30d

        base_prices = {"BTC/USDT": 63820.0, "ETH/USDT": 3245.0, "SOL/USDT": 138.5}
        step_count = 0

        while True:
            await asyncio.sleep(3)
            step_count += 1

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

            realtime_pnl = sum(p["pnl"] for p in dash._state.positions)
            dash._state.total_pnl = realtime_pnl
            cumulative_pnl += uniform(-2, 8)
            daily_pnl = cumulative_pnl - daily_start_pnl
            total_assets = 100000.0 + cumulative_pnl
            daily_pct = (daily_pnl / max(100000.0 + daily_start_pnl, 1)) * 100

            dash._state.pnl_metrics = {
                "total_assets": round(total_assets, 2),
                "realtime": round(realtime_pnl, 2),
                "daily": round(daily_pnl, 2),
                "daily_pct": round(daily_pct, 2),
                "monthly": round(cumulative_pnl, 2),
                "monthly_pct": round((cumulative_pnl / 100000.0) * 100, 2),
                "total": round(cumulative_pnl, 2),
                "total_pct": round((cumulative_pnl / 100000.0) * 100, 2),
            }

            pnl_history_30d.append({"i": len(pnl_history_30d), "value": round(cumulative_pnl, 2)})
            if len(pnl_history_30d) > 720:
                pnl_history_30d = pnl_history_30d[-720:]
            dash._state.pnl_history["30d"] = pnl_history_30d

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

            if step_count % 60 == 0:
                daily_start_pnl = cumulative_pnl

    asyncio.create_task(demo_loop())
    print()
    print("[DEMO] Vulpes Trader Dashboard")
    print("=" * 40)
    print(">> http://127.0.0.1:%d" % PORT)
    print(">> 3s自动更新, PnL 与持仓实时联动")
    print()

    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        await dash.stop()


if __name__ == "__main__":
    asyncio.run(main())
