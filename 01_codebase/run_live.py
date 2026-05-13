"""启动实盘 — 完整交易链路 + Dashboard 实时数据"""
import asyncio, logging, os, json
os.environ["VULPES_DASHBOARD_PORT"] = "8778"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("vulpes.launch")


def _collect_status(orch, config):
    return {
        "status": "running" if orch.running else "stopped",
        "mode": config.mode,
        "active_positions": orch.position_manager.position_count,
        "max_positions": orch.risk_manager.config.get("max_total_positions", 5),
        "uptime_seconds": 0,
        "circuit_breaker_tripped": False,
    }


def _collect_positions(orch):
    positions = []
    for sym, pos in orch.position_manager._positions.items():
        positions.append({
            "symbol": sym,
            "side": pos.side,
            "entry_price": pos.entry_price,
            "current_price": pos.entry_price,
            "quantity": pos.quantity,
            "leverage": pos.leverage,
            "pnl": 0,
            "pnl_pct": 0,
            "stop_loss": 0,
            "take_profit": 0,
        })
    return positions


def _collect_performance(orch):
    return {
        "total_pnl": 0,
        "win_rate": 0,
        "trade_count": 0,
        "daily_loss": 0,
    }


def _collect_signals(orch):
    return []


async def main():
    from vulpes_trader.orchestrator import VulpesOrchestrator
    from vulpes_trader.config import config
    from vulpes_trader.dashboard.server import DashboardServer

    logger.info("=== Vulpes Trader 实盘启动 ===")
    logger.info("模式: %s", config.mode)

    orch = VulpesOrchestrator()
    await orch.start()

    # 验证 KlineEngine 数据
    for sym in orch.ws_manager.symbols[:2]:
        for tf in orch.ws_manager.timeframes[:2]:
            df = orch.kline_engine.get_klines(sym, tf)
            count = len(df) if df is not None else 0
            logger.info("Kline [%s %s]: %d rows", sym, tf, count)
            if count >= 2:
                logger.info("  最新close: %.2f", df["close"].iloc[-1])

    # 验证信号层
    logger.info("--- 信号测试 ---")
    for sym in orch.ws_manager.symbols[:1]:
        sig = await orch.trend_follower.generate(sym)
        if sig:
            logger.info("  %s: %s conf=%.2f", sym, sig.direction.value, sig.confidence)
        else:
            logger.info("  %s: 信号未就绪", sym)

    logger.info("--- 实盘就绪 ---")

    # Dashboard
    PORT = int(os.environ["VULPES_DASHBOARD_PORT"])
    dash = DashboardServer(port=PORT)

    # 注册所有回调
    dash.register_callbacks(
        status=lambda: _collect_status(orch, config),
        positions=lambda: _collect_positions(orch),
        performance=lambda: _collect_performance(orch),
        signals=lambda: _collect_signals(orch),
    )
    await dash.start()
    logger.info("Dashboard: http://127.0.0.1:%d", PORT)

    # 定时推送数据到 Dashboard WebSocket
    async def push_loop():
        while orch.running:
            try:
                # 从 orchestrator 读实时价格
                for sym in orch.ws_manager.symbols:
                    latest = orch.kline_engine.get_latest(sym, "5m")
                    if latest is not None:
                        price = latest["close"]
                        # 更新持仓价格
                        for pos in dash._state.positions:
                            if pos["symbol"] == sym:
                                pos["current_price"] = float(price)
                                side = 1 if pos["side"] == "long" else -1
                                pos["pnl"] = round((price - pos["entry_price"]) * pos["quantity"] * pos["leverage"] * side, 2)
                                pos["pnl_pct"] = round(((price - pos["entry_price"]) / pos["entry_price"]) * 100, 2)

                # 推送实时数据
                await dash.broadcast("positions", _collect_positions(orch))
                await dash.broadcast("status", _collect_status(orch, config))

            except Exception as e:
                logger.error("Dash push error: %s", e)

            await asyncio.sleep(3)  # 每 3 秒刷新

    asyncio.create_task(push_loop())

    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        await dash.stop()
        await orch.stop()


if __name__ == "__main__":
    asyncio.run(main())
