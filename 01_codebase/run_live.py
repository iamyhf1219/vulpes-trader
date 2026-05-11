"""启动实盘 — 验证完整交易链路"""
import asyncio, logging, os
os.environ["VULPES_DASHBOARD_PORT"] = "8778"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("vulpes.launch")

async def main():
    from vulpes_trader.orchestrator import VulpesOrchestrator
    from vulpes_trader.config import config

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

    # 验证信号层可以生成信号
    logger.info("--- 信号测试 ---")
    for sym in orch.ws_manager.symbols[:1]:
        sig = await orch.trend_follower.generate(sym)
        if sig:
            logger.info("  %s: %s conf=%.2f", sym, sig.direction.value, sig.confidence)
        else:
            logger.info("  %s: 信号未就绪（可能需要更多K线）", sym)

    logger.info("--- 实盘就绪 ---")

    # Dashboard
    from vulpes_trader.dashboard.server import create_dashboard
    dash = create_dashboard(port=int(os.environ["VULPES_DASHBOARD_PORT"]))
    dash.register_callbacks(
        status=lambda: {
            "status": "running" if orch.running else "stopped",
            "mode": config.mode,
            "active_positions": orch.position_manager.position_count,
            "max_positions": orch.risk_manager.config.get("max_total_positions", 5),
        }
    )
    await dash.start()
    logger.info("Dashboard: http://127.0.0.1:%s", os.environ["VULPES_DASHBOARD_PORT"])

    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        await dash.stop()
        await orch.stop()

if __name__ == "__main__":
    asyncio.run(main())
