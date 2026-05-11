"""OI 与资金费率采集 — REST API 定时拉取"""

import asyncio
import logging
from typing import Callable, List, Optional
from dataclasses import dataclass
from vulpes_trader.config import config
from vulpes_trader.utils.retry import async_retry

logger = logging.getLogger("vulpes.supplementary")


@dataclass
class OIDataPoint:
    symbol: str
    oi: float
    oi_change_pct: float
    timestamp: int


@dataclass
class FundingRateDataPoint:
    symbol: str
    rate: float
    next_payment_time: int
    timestamp: int


class SupplementaryCollector:
    """辅助数据采集器 — OI + 资金费率"""

    def __init__(self, symbols: List[str]):
        self.symbols = symbols
        self._exchange = None
        self._running = False
        self._handlers: List[Callable] = []

    async def _ensure_exchange(self):
        if self._exchange is None:
            # Lazy import to avoid startup dependency on ccxt REST
            from ccxt import binance as BinanceRest
            exchange_config = config.exchange_config
            exchange_config["options"] = {"defaultType": "future" if config.mode == "mainnet" else "spot"}
            if config.mode == "mainnet":
                exchange_config["urls"] = {}
            if "api" not in exchange_config["urls"]:
                exchange_config["urls"]["api"] = {}
            self._exchange = BinanceRest(exchange_config)
            if config.mode == "testnet":
                self._exchange.set_sandbox_mode(True)

    async def start(self, oi_interval: int = 60, funding_interval: int = 3600):
        """启动定时采集"""
        self._running = True
        asyncio.create_task(self._oi_loop(oi_interval))
        asyncio.create_task(self._funding_loop(funding_interval))

    async def fetch_open_interest(self, symbol: str) -> Optional[OIDataPoint]:
        """获取单个币种 OI"""
        try:
            await self._ensure_exchange()
            result = await async_retry(
                self._exchange.fetch_open_interest, max_retries=2,
                symbol=symbol,
            )
            return OIDataPoint(
                symbol=symbol,
                oi=float(result.get("openInterest", 0)),
                oi_change_pct=0.0,
                timestamp=int(result.get("timestamp", 0)),
            )
        except Exception as e:
            logger.warning("获取 OI 失败 %s: %s", symbol, e)
            return None

    async def fetch_funding_rate(self, symbol: str) -> Optional[FundingRateDataPoint]:
        """获取资金费率"""
        try:
            await self._ensure_exchange()
            result = await async_retry(
                self._exchange.fetch_funding_rate, max_retries=2,
                symbol=symbol,
            )
            return FundingRateDataPoint(
                symbol=symbol,
                rate=float(result.get("fundingRate", 0)),
                next_payment_time=int(result.get("nextFundingTime", 0)),
                timestamp=int(result.get("timestamp", 0)),
            )
        except Exception as e:
            logger.warning("获取资金费率失败 %s: %s", symbol, e)
            return None

    async def _oi_loop(self, interval: int):
        """OI 定时采集"""
        while self._running:
            for symbol in self.symbols:
                data = await self.fetch_open_interest(symbol)
                if data:
                    for handler in self._handlers:
                        await handler(data)
            await asyncio.sleep(interval)

    async def _funding_loop(self, interval: int):
        """资金费率定时采集"""
        while self._running:
            for symbol in self.symbols:
                data = await self.fetch_funding_rate(symbol)
                if data:
                    for handler in self._handlers:
                        await handler(data)
            await asyncio.sleep(interval)

    def on_data(self, handler: Callable):
        """注册数据回调"""
        self._handlers.append(handler)

    async def close(self):
        self._running = False
        if self._exchange:
            pass  # sync ccxt, no close needed
        logger.info("补充数据采集器已停止")
        """安全关闭"""
        self._running = False
        if self._exchange:
            await self._exchange.close()
