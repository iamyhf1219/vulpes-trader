"""WebSocket 连接管理器 — 通过 ccxt Pro 订阅实时行情"""

import asyncio
import logging
from typing import List, Callable, Awaitable, Optional, Dict, Any
from ccxt.pro import binance as Binance
from vulpes_trader.config import config
from vulpes_trader.utils.retry import async_retry

logger = logging.getLogger("vulpes.ws")


class WSManager:
    """WebSocket 连接管理，支持自动重连"""

    def __init__(self, symbols: List[str], timeframes: List[str]):
        self.symbols = symbols
        self.timeframes = timeframes
        self.exchange: Optional[Binance] = None
        self._running = False
        self._ticker_handlers: List[Callable] = []
        self._ohlcv_handlers: List[Callable] = []

    async def connect(self):
        """建立连接（指数退避重连）"""
        self._running = True
        await async_retry(self._do_connect, max_retries=5)

    async def _do_connect(self):
        """实际连接逻辑"""
        exchange_config = config.exchange_config
        self.exchange = Binance({
            "apiKey": exchange_config["apiKey"],
            "secret": exchange_config["secret"],
            "options": exchange_config.get("options", {}),
        })
        if "urls" in exchange_config:
            self.exchange.urls = exchange_config["urls"]
        logger.info("WebSocket 连接成功: symbols=%s", self.symbols[:3])

    async def subscribe_tickers(self, handler: Callable[[Dict], Awaitable[None]]):
        """订阅实时 Ticker"""
        self._ticker_handlers.append(handler)
        if not self._running:
            asyncio.create_task(self._ticker_loop())

    async def _ticker_loop(self):
        """Ticker 订阅循环（自动重连）"""
        while self._running:
            try:
                if not self.exchange:
                    await self.connect()
                for symbol in self.symbols:
                    ticker = await self.exchange.watch_ticker(symbol)
                    for handler in self._ticker_handlers:
                        await handler(ticker)
            except Exception as e:
                logger.error("Ticker 订阅中断: %s, 5秒后重连", e)
                await asyncio.sleep(5)

    async def subscribe_ohlcv(self, handler: Callable[[Dict], Awaitable[None]]):
        """订阅 K 线"""
        self._ohlcv_handlers.append(handler)
        if not self._running:
            asyncio.create_task(self._ohlcv_loop())

    async def _ohlcv_loop(self):
        """OHLCV 订阅循环"""
        while self._running:
            try:
                if not self.exchange:
                    await self.connect()
                for symbol in self.symbols:
                    for tf in self.timeframes:
                        ohlcv = await self.exchange.watch_ohlcv(symbol, tf)
                        for handler in self._ohlcv_handlers:
                            await handler({"symbol": symbol, "timeframe": tf, "data": ohlcv})
            except Exception as e:
                logger.error("OHLCV 订阅中断: %s, 5秒后重连", e)
                await asyncio.sleep(5)

    async def close(self):
        """安全关闭"""
        self._running = False
        if self.exchange:
            await self.exchange.close()
            logger.info("WebSocket 连接已关闭")
