"""启动 Vulpes Trader Dashboard Demo 模式（带实时模拟数据）"""
import sys
for k in list(sys.modules.keys()):
    if "vulpes_trader.dashboard" in k:
        del sys.modules[k]

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

PORT = 8771

async def main():
    from vulpes_trader.dashboard.server import DashboardServer, _generate_demo_data

    dash = DashboardServer(port=PORT)
    demo_state = _generate_demo_data()
    dash.inject_state(demo_state)

    await dash.start()

    async def demo_loop():
        from random import uniform
        base_prices = {"BTC/USDT": 63820.0, "ETH/USDT": 3245.0, "SOL/USDT": 138.5}
        while True:
            await asyncio.sleep(3)
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
            dash._state.total_pnl = sum(p["pnl"] for p in dash._state.positions)
            await dash.broadcast("positions", dash._state.positions)
            await dash.broadcast("status", {
                "total_pnl": round(dash._state.total_pnl, 2),
                "active_positions": len(dash._state.positions),
            })

    asyncio.create_task(demo_loop())
    print()
    print("[DEMO] Vulpes Trader Dashboard")
    print("=" * 40)
    print(">> http://127.0.0.1:%d" % PORT)
    print(">> 3秒自动更新, WebSocket 实时推送")
    print()

    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        await dash.stop()

if __name__ == "__main__":
    asyncio.run(main())
