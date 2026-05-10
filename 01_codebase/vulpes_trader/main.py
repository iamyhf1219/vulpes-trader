"""Vulpes Trader 入口"""

import asyncio
import logging
from vulpes_trader.config import config
from vulpes_trader.orchestrator import VulpesOrchestrator

logger = logging.getLogger("vulpes")


async def main():
    logger.info("=== Vulpes Trader 启动 ===")
    logger.info("模式: %s", config.mode)
    
    orchestrator = VulpesOrchestrator()
    await orchestrator.start()
    
    try:
        # 保持运行
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        logger.info("收到停止信号，正在安全关闭...")
    finally:
        await orchestrator.stop()


def run():
    """同步入口，处理 Ctrl+C"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("用户中断，正在退出...")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run()
