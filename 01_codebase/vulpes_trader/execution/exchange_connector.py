"""交易所连接器 — ccxt 封装，testnet sync / mainnet async"""

import asyncio
import logging
import functools
from typing import Optional, Dict, List, Any

import ccxt.async_support as ccxt_async
import ccxt as ccxt_sync

from vulpes_trader.config import config
from vulpes_trader.utils.retry import async_retry

logger = logging.getLogger("vulpes.execution.exchange")

RETRYABLE_ERRORS = (
    ccxt_sync.NetworkError, ccxt_sync.RequestTimeout, ccxt_sync.BadResponse,
    ccxt_sync.ExchangeNotAvailable, ccxt_sync.OnMaintenance, ccxt_sync.RateLimitExceeded,
    ConnectionError, TimeoutError, OSError,
)


class ExchangeConnector:
    """
    交易所连接器

    testnet → ccxt sync + asyncio.to_thread（async 版 testnet 有 ccxt bug）
    mainnet → ccxt async
    """

    def __init__(
        self,
        exchange_id: Optional[str] = None,
        mode: Optional[str] = None,
        config_override: Optional[Dict[str, Any]] = None,
    ):
        self.mode = mode or config.mode
        self.exchange_id = exchange_id or ("binance" if self.mode == "testnet" else "binanceusdm")
        self._config_override = config_override
        self._exchange = None
        self._connected = False
        self._connecting = False
        self._markets_loaded = False
        self.request_count = 0
        self.reconnect_count = 0

    def _build_config(self) -> Dict[str, Any]:
        if self._config_override:
            return self._config_override
        return {
            "apiKey": config.exchange_config.get("apiKey", ""),
            "secret": config.exchange_config.get("secret", ""),
            "password": config.exchange_config.get("password", ""),
            "options": {
                "defaultType": "future" if self.exchange_id == "binanceusdm" else "spot",
                "adjustForTimeDifference": True,
            },
            "enableRateLimit": True,
        }

    async def _exec(self, method: str, *args, **kwargs):
        """统一调用：testnet 用 sync thread, mainnet 用 async"""
        meth = getattr(self._exchange, method)
        if self.mode == "testnet":
            return await asyncio.to_thread(functools.partial(meth, *args, **kwargs))
        return await meth(*args, **kwargs)

    async def connect(self):
        if self._connected and self._exchange:
            return
        self._connecting = True
        try:
            cfg = self._build_config()
            if self.mode == "testnet":
                cls = getattr(ccxt_sync, self.exchange_id)
                self._exchange = cls(cfg)
                self._exchange.set_sandbox_mode(True)
                await asyncio.to_thread(self._exchange.load_markets)
            else:
                cls = getattr(ccxt_async, self.exchange_id)
                self._exchange = cls(cfg)
                await self._exchange.load_markets()
            self._connected = True
            self._markets_loaded = True
            self._connecting = False
            logger.info("交易所 %s 连接成功 [%s] markets=%d", self.exchange_id, self.mode, len(self._exchange.symbols))
        except Exception as e:
            self._connected = False
            self._connecting = False
            logger.error("交易所连接失败: %s", e)
            raise

    async def _call_with_retry(self, method: str, *args, **kwargs) -> Any:
        return await async_retry(
            functools.partial(self._exec, method, *args, **kwargs),
            max_retries=3, base_delay=1.0, max_delay=30.0,
            exceptions=RETRYABLE_ERRORS,
        )

    async def create_market_order(self, symbol: str, side: str, amount: float,
                                   params: Optional[Dict] = None) -> Dict:
        return await self._call_with_retry("create_market_order", symbol, side, amount, params or {})

    async def create_limit_order(self, symbol: str, side: str, amount: float,
                                  price: float, params: Optional[Dict] = None) -> Dict:
        return await self._call_with_retry("create_limit_order", symbol, side, amount, price, params or {})

    async def cancel_order(self, order_id: str, symbol: str) -> Dict:
        return await self._call_with_retry("cancel_order", order_id, symbol)

    async def fetch_order(self, order_id: str, symbol: str) -> Dict:
        return await self._call_with_retry("fetch_order", order_id, symbol)

    async def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        return await self._call_with_retry("fetch_open_orders", symbol)

    async def fetch_positions(self, symbols: Optional[List[str]] = None,
                               params: Optional[Dict] = None) -> List[Dict]:
        return await self._call_with_retry("fetch_positions", symbols or [], params or {})

    async def fetch_balance(self, params: Optional[Dict] = None) -> Dict:
        return await self._call_with_retry("fetch_balance", params or {})

    async def close(self):
        if self._exchange:
            try:
                if self.mode != "testnet":
                    await self._exchange.close()
            except Exception:
                pass
            self._exchange = None
            self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected and self._exchange is not None
