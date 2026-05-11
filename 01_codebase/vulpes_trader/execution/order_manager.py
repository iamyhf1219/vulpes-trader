"""订单管理器 — 发送和跟踪订单"""

import asyncio
import logging
from typing import Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger("vulpes.execution.order")


class OrderStatus(Enum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


@dataclass
class Order:
    symbol: str
    side: str  # 'buy' | 'sell'
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    order_id: Optional[str] = None
    exchange_order_id: Optional[str] = None  # 交易所返回的 ID
    filled_quantity: float = 0.0
    avg_fill_price: Optional[float] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: Optional[str] = None
    error: Optional[str] = None


class OrderManager:
    """订单管理器 — 订单生命周期管理"""

    def __init__(self, exchange=None):
        self._exchange = exchange
        self._orders: Dict[str, Order] = {}

    # ─── 本地订单管理（保持向后兼容） ─────────────────────

    def create_order(
        self,
        symbol: str,
        side: str,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> Order:
        """创建订单（仅本地）"""
        order = Order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            order_id=f"ord_{datetime.now(timezone.utc).timestamp()}_{hash(symbol) % 10000}",
        )
        self._orders[order.order_id] = order
        logger.info("创建订单 %s: %s %s %.4f", order.order_id, symbol, side, quantity)
        return order

    def get_order(self, order_id: str) -> Optional[Order]:
        """获取订单"""
        return self._orders.get(order_id)

    def update_order(
        self, order_id: str, status: OrderStatus,
        filled_qty: Optional[float] = None,
        avg_price: Optional[float] = None,
        error: Optional[str] = None,
    ):
        """更新订单状态"""
        order = self._orders.get(order_id)
        if order is None:
            logger.warning("订单 %s 不存在", order_id)
            return

        order.status = status
        order.updated_at = datetime.now(timezone.utc).isoformat()

        if filled_qty is not None:
            order.filled_quantity = filled_qty
        if avg_price is not None:
            order.avg_fill_price = avg_price
        if error is not None:
            order.error = error

    def cancel_order(self, order_id: str) -> bool:
        """取消订单（仅本地，同步方法，保持向后兼容）

        需要同时取消远程订单时，请使用 cancel_remote_order()
        """
        order = self._orders.get(order_id)
        if order and order.status in (OrderStatus.PENDING, OrderStatus.OPEN):
            order.status = OrderStatus.CANCELLED
            order.updated_at = datetime.now(timezone.utc).isoformat()
            logger.info("订单已取消（本地）: %s", order_id)
            return True
        return False

    def get_active_orders(self, symbol: Optional[str] = None) -> list:
        """获取活跃订单"""
        active = []
        for oid, order in self._orders.items():
            if order.status in (OrderStatus.PENDING, OrderStatus.OPEN):
                if symbol is None or order.symbol == symbol:
                    active.append(order)
        return active

    @property
    def total_open_orders(self) -> int:
        """获取未成交订单数"""
        return len(self.get_active_orders())

    # ─── 实盘订单操作（ExchangeConnector 注入时生效） ───────

    async def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
    ) -> Order:
        """提交市价单到交易所

        Args:
            symbol: 交易对
            side: buy / sell
            quantity: 数量

        Returns:
            Order: 更新后的本地订单

        Raises:
            RuntimeError: 未注入 ExchangeConnector
        """
        if self._exchange is None:
            raise RuntimeError("ExchangeConnector 未注入，无法提交实盘订单")

        order = self.create_order(symbol, side, OrderType.MARKET, quantity)

        try:
            result = await self._exchange.create_market_order(symbol, side, quantity)
            self._update_order_from_ccxt(order, result)
            logger.info(
                "市价单已提交 %s [%s]: id=%s qty=%.4f price=%s",
                symbol, side, result.get("id", "?"),
                result.get("filled", 0), result.get("price", "?"),
            )
        except Exception as e:
            order.status = OrderStatus.REJECTED
            order.error = str(e)
            order.updated_at = datetime.now(timezone.utc).isoformat()
            logger.error("市价单提交失败 %s %s: %s", symbol, side, e)

        return order

    async def place_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
    ) -> Order:
        """提交限价单到交易所

        Args:
            symbol: 交易对
            side: buy / sell
            quantity: 数量
            price: 限价

        Returns:
            Order: 更新后的本地订单

        Raises:
            RuntimeError: 未注入 ExchangeConnector
        """
        if self._exchange is None:
            raise RuntimeError("ExchangeConnector 未注入，无法提交实盘订单")

        order = self.create_order(symbol, side, OrderType.LIMIT, quantity, price=price)

        try:
            result = await self._exchange.create_limit_order(symbol, side, quantity, price)
            self._update_order_from_ccxt(order, result)
            logger.info(
                "限价单已提交 %s [%s]: id=%s @%.2f qty=%.4f",
                symbol, side, result.get("id", "?"), price, quantity,
            )
        except Exception as e:
            order.status = OrderStatus.REJECTED
            order.error = str(e)
            order.updated_at = datetime.now(timezone.utc).isoformat()
            logger.error("限价单提交失败 %s %s @%.2f: %s", symbol, side, price, e)

        return order

    async def cancel_remote_order(self, order_id: str) -> bool:
        """取消远程订单（同时取消远程和本地）

        Args:
            order_id: 本地订单 ID

        Returns:
            True 如果取消成功
        """
        order = self._orders.get(order_id)
        if order is None:
            logger.warning("订单 %s 不存在", order_id)
            return False

        if order.status not in (OrderStatus.PENDING, OrderStatus.OPEN):
            logger.warning("订单 %s 状态 %s 不可取消", order_id, order.status.value)
            return False

        # 先取消远程订单
        if self._exchange is not None and order.exchange_order_id:
            try:
                await self._exchange.cancel_order(order.exchange_order_id, order.symbol)
                logger.info("远程订单已取消: %s", order.exchange_order_id)
            except Exception as e:
                logger.warning("取消远程订单失败 %s: %s", order.exchange_order_id, e)

        # 更新本地状态
        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now(timezone.utc).isoformat()
        logger.info("订单已取消（本地）: %s", order_id)
        return True

    async def sync_orders(self, symbol: Optional[str] = None) -> int:
        """从交易所拉取订单状态并更新本地

        Args:
            symbol: 交易对过滤

        Returns:
            更新的订单数量

        Raises:
            RuntimeError: 未注入 ExchangeConnector
        """
        if self._exchange is None:
            raise RuntimeError("ExchangeConnector 未注入")

        try:
            open_orders = await self._exchange.fetch_open_orders(symbol)
            updated_count = 0

            for ccxt_order in open_orders:
                exchange_id = ccxt_order.get("id", "")
                local_order = self._find_order_by_exchange_id(exchange_id)
                if local_order:
                    self._update_order_from_ccxt(local_order, ccxt_order)
                    updated_count += 1

            if updated_count > 0:
                logger.debug("已同步 %d 个订单状态", updated_count)
            return updated_count

        except Exception as e:
            logger.error("同步订单状态失败: %s", e)
            return 0

    async def sync_positions(self, symbols: Optional[list] = None) -> list:
        """从交易所拉取持仓

        Args:
            symbols: 交易对列表，不传则查全部

        Returns:
            持仓列表（原始 ccxt 字典）

        Raises:
            RuntimeError: 未注入 ExchangeConnector
        """
        if self._exchange is None:
            raise RuntimeError("ExchangeConnector 未注入")

        try:
            positions = await self._exchange.fetch_positions(symbols)
            logger.debug("已获取 %d 个持仓", len(positions))
            return positions
        except Exception as e:
            logger.error("获取持仓失败: %s", e)
            return []

    # ─── 内部辅助 ───────────────────────────────────────────

    def _update_order_from_ccxt(self, order: Order, ccxt_result: Dict) -> None:
        """用 ccxt 返回的数据更新本地订单"""
        ccxt_status = ccxt_result.get("status", "")
        status_map = {
            "open": OrderStatus.OPEN,
            "closed": OrderStatus.FILLED,
            "filled": OrderStatus.FILLED,
            "canceled": OrderStatus.CANCELLED,
            "cancelled": OrderStatus.CANCELLED,
            "expired": OrderStatus.EXPIRED,
            "rejected": OrderStatus.REJECTED,
            "new": OrderStatus.OPEN,
            "partially_filled": OrderStatus.OPEN,
        }
        order.status = status_map.get(ccxt_status, order.status)
        order.updated_at = datetime.now(timezone.utc).isoformat()

        filled = ccxt_result.get("filled")
        if filled is not None:
            order.filled_quantity = float(filled)

        price = ccxt_result.get("price") or ccxt_result.get("average")
        if price is not None:
            order.avg_fill_price = float(price)

        exchange_id = ccxt_result.get("id")
        if exchange_id:
            order.exchange_order_id = str(exchange_id)

    def _find_order_by_exchange_id(self, exchange_id: str) -> Optional[Order]:
        """通过交易所订单 ID 查找本地订单"""
        for order in self._orders.values():
            if order.exchange_order_id == exchange_id:
                return order
        return None
