"""交易所连接器 — ccxt 封装，支持 testnet/mainnet 切换和断线重连"""

import asyncio
import logging
import functools
from typing import Optional, Dict, List, Any

import ccxt.async_support as ccxt_async
import ccxt as ccxt_sync

from vulpes_trader.config import config
from vulpes_trader.utils.retry import async_retry

logger = logging.getLogger("vulpes.execution.exchange")

# ccxt 可重试的网络异常
RETRYABLE_ERRORS = (
    ccxt_sync.NetworkError,
    ccxt_sync.RequestTimeout,
    ccxt_sync.BadResponse,
    ccxt_sync.ExchangeNotAvailable,
    ccxt_sync.OnMaintenance,
    ccxt_sync.RateLimitExceeded,
    ConnectionError,
    TimeoutError,
    OSError,
)


class ExchangeConnector:
    """交易所连接器

    封装 ccxt 交易所连接，提供统一接口。
    支持 testnet/mainnet 模式切换，所有网络调用自动重试。

    Attributes:
        exchange_id: 交易所标识（默认 binanceusdm）
        mode: 运行模式 testnet | mainnet
    """

    def __init__(
        self,
        exchange_id: str = "binanceusdm",
        mode: Optional[str] = None,
        config_override: Optional[Dict[str, Any]] = None,
    ):
        self.exchange_id = exchange_id
        self.mode = mode or config.mode
        self._config_override = config_override

        self._exchange: Optional[ccxt_async.Exchange] = None
        self._connected: bool = False
        self._connecting: bool = False
        self._markets_loaded: bool = False

        # 统计
        self.request_count: int = 0
        self.reconnect_count: int = 0

    # ─── 配置构建 ────────────────────────────────────────────

    def _build_ccxt_config(self) -> Dict[str, Any]:
        """构建 ccxt 配置字典"""
        if self._config_override is not None:
            return self._config_override

        base = {
            "apiKey": config.exchange_config.get("apiKey", ""),
            "secret": config.exchange_config.get("secret", ""),
            "password": config.exchange_config.get("password", ""),
            "options": {
                "defaultType": "swap",
                "adjustForTimeDifference": True,
            },
            "enableRateLimit": True,
        }

        if self.mode == "testnet":
            base["urls"] = {
                "api": {
                    "public": "https://testnet.binancefuture.com/fapi/v1",
                    "private": "https://testnet.binancefuture.com/fapi/v1",
                },
            }

        return base

    # ─── 连接生命周期 ────────────────────────────────────────

    async def connect(self) -> None:
        """建立交易所连接并加载市场数据"""
        if self._connected and self._exchange:
            logger.debug("交易所已连接，跳过")
            return

        if self._connecting:
            logger.debug("交易所正在连接中，等待...")
            while self._connecting:
                await asyncio.sleep(0.1)
            return

        self._connecting = True
        try:
            exchange_class = getattr(ccxt_async, self.exchange_id)
            ccxt_config = self._build_ccxt_config()

            self._exchange = exchange_class(ccxt_config)

            logger.info("交易所 %s 连接中（模式: %s）...", self.exchange_id, self.mode)
            markets = await self._exchange.load_markets()
            self._markets_loaded = True
            self._connected = True
            logger.info(
                "交易所连接成功: %s (%s), %d 个交易对",
                self.exchange_id, self.mode, len(markets) if markets else 0,
            )
        except Exception as e:
            logger.error("交易所连接失败: %s", e)
            self._exchange = None
            raise
        finally:
            self._connecting = False

    async def close(self) -> None:
        """关闭交易所连接"""
        self._connected = False
        self._markets_loaded = False
        exchange = self._exchange
        self._exchange = None
        if exchange:
            try:
                await exchange.close()
            except Exception as e:
                logger.warning("关闭交易所连接时出错: %s", e)
        logger.info("交易所连接已关闭")

    async def _ensure_connected(self) -> None:
        """确保连接有效，必要时重连"""
        if not self._exchange or not self._connected:
            await self.connect()

    async def _reconnect(self) -> None:
        """断线重连"""
        self.reconnect_count += 1
        logger.warning("断线重连中（第 %d 次）...", self.reconnect_count)
        await self.close()
        await self.connect()

    # ─── 核心调用方法 ────────────────────────────────────────

    async def _call_with_retry(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
        """执行 ccxt 方法调用，带自动重试和断线重连

        用 lambda 封装方法调用，避免 *args 与 async_retry 参数位置冲突。
        """
        await self._ensure_connected()
        self.request_count += 1

        method = getattr(self._exchange, method_name)

        async def _call():
            return await method(*args, **kwargs)

        try:
            result = await async_retry(
                _call,
                max_retries=3,
                base_delay=0.5,
                max_delay=30.0,
                exceptions=RETRYABLE_ERRORS,
            )
            self.reconnect_count = 0
            return result

        except ccxt_sync.BaseError as e:
            logger.error("交易所调用 %s 失败: %s", method_name, e)

            if isinstance(e, (ccxt_sync.NetworkError, ccxt_sync.ExchangeNotAvailable)):
                try:
                    await self._reconnect()
                except Exception as reconnect_err:
                    logger.error("重连失败: %s", reconnect_err)

            raise

    # ─── 公开 API ────────────────────────────────────────────

    async def create_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """创建市价单"""
        logger.info("市价单 %s %s %.4f", symbol, side, quantity)
        return await self._call_with_retry(
            "create_market_order", symbol, side, quantity, params or {},
        )

    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """创建限价单"""
        logger.info("限价单 %s %s %.4f @ %.2f", symbol, side, quantity, price)
        return await self._call_with_retry(
            "create_limit_order", symbol, side, quantity, price, params or {},
        )

    async def cancel_order(
        self,
        order_id: str,
        symbol: Optional[str] = None,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """取消订单"""
        logger.info("取消订单 %s (%s)", order_id, symbol or "?")
        return await self._call_with_retry("cancel_order", order_id, symbol, params or {})

    async def fetch_order(
        self,
        order_id: str,
        symbol: Optional[str] = None,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """查询订单状态"""
        return await self._call_with_retry("fetch_order", order_id, symbol, params or {})

    async def fetch_open_orders(
        self,
        symbol: Optional[str] = None,
        params: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """查询未成交订单"""
        return await self._call_with_retry("fetch_open_orders", symbol, params or {})

    async def fetch_positions(
        self,
        symbols: Optional[List[str]] = None,
        params: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """查询持仓"""
        return await self._call_with_retry("fetch_positions", symbols, params or {})

    async def fetch_balance(self, params: Optional[Dict] = None) -> Dict[str, Any]:
        """查询账户余额"""
        return await self._call_with_retry("fetch_balance", params or {})

    @property
    def is_connected(self) -> bool:
        """连接状态"""
        return self._connected and self._exchange is not None
