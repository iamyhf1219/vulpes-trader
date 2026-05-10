"""Vulpes Trader 入口"""

import asyncio
import logging
from vulpes_trader.config import config

logger = logging.getLogger("vulpes")


async def main():
    logger.info("=== Vulpes Trader 启动 ===")
    logger.info("模式: %s", config.mode)
    
    try:
        # TODO: Phase 2+ - 启动各层组件
        logger.info("基建就绪，等待后续模块加载...")
        await asyncio.Event().wait()  # 永久运行
    except KeyboardInterrupt:
        logger.info("收到停止信号，正在安全关闭...")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(main())
