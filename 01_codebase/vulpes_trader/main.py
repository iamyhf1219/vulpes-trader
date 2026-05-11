"""Vulpes Trader 入口"""

import asyncio
import logging
from vulpes_trader.config import config
from vulpes_trader.orchestrator import VulpesOrchestrator

logger = logging.getLogger("vulpes")


async def main(args=None):
    logger.info("=== Vulpes Trader 启动 ===")
    logger.info("模式: %s", config.mode)

    orchestrator = VulpesOrchestrator()
    await orchestrator.start()

    dash = None
    if args and args.dashboard:
        dash = await _start_dashboard(orchestrator)

    try:
        # 保持运行
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        logger.info("收到停止信号，正在安全关闭...")
    finally:
        if dash:
            await dash.stop()
        await orchestrator.stop()


async def _start_dashboard(orchestrator: VulpesOrchestrator):
    """启动 Dashboard 并注册数据回调"""
    from vulpes_trader.dashboard.server import start_dashboard

    dash = start_dashboard()

    # 注册数据注入回调
    def get_status():
        return {
            "status": "running" if orchestrator.running else "stopped",
            "mode": config.mode,
            "uptime_seconds": 0.0,
            "active_positions": orchestrator.position_manager.position_count,
            "max_positions": orchestrator.risk_manager.config.get("max_total_positions", 5),
            "circuit_breaker_tripped": orchestrator.risk_manager.circuit_breaker.is_tripped(),
            "max_leverage": orchestrator.risk_manager.config.get("max_leverage", 20),
        }

    def get_positions():
        positions = orchestrator.position_manager.active_positions
        return [
            {
                "symbol": p.symbol,
                "side": p.side,
                "size": p.size,
                "entry_price": p.entry_price,
                "current_price": 0.0,  # TODO: pull from kline engine
                "pnl": p.pnl,
                "leverage": p.leverage,
            }
            for p in positions.values()
        ]

    def get_performance():
        return {
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "trade_count": 0,
            "daily_loss": 0.0,
        }

    def get_signals():
        history = getattr(orchestrator.fusion, "_signal_history", [])
        return [
            {
                "direction": sig.direction.value,
                "confidence": sig.confidence,
                "source": sig.source,
                "timestamp": sig.timestamp,
            }
            for sig in history[-50:]
        ]

    def get_config():
        return {
            "mode": config.mode,
            "symbols": getattr(orchestrator.ws_manager, "symbols", []),
            "timeframes": [],
            "fusion_weights": dict(getattr(orchestrator.fusion, "weights", {})),
            "risk": dict(getattr(orchestrator.risk_manager, "config", {})),
        }

    dash.register_callbacks(
        status=get_status,
        positions=get_positions,
        performance=get_performance,
        signals=get_signals,
        config=get_config,
    )

    await dash.start()

    # 日志转发
    class DashLogHandler(logging.Handler):
        def emit(self, record):
            msg = self.format(record)
            asyncio.ensure_future(
                dash.broadcast("log", {
                    "level": record.levelname,
                    "message": msg,
                    "timestamp": getattr(record, "asctime", ""),
                    "source": record.name,
                })
            )

    handler = DashLogHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger("vulpes").addHandler(handler)

    return dash


def run():
    """同步入口，处理 Ctrl+C"""
    import argparse
    parser = argparse.ArgumentParser(description="Vulpes Trader")
    parser.add_argument("--dashboard", action="store_true", help="启动 Web Dashboard")
    args = parser.parse_args()

    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        logger.info("用户中断，正在退出...")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run()
