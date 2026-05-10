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

    def create_order(
        self,
        symbol: str,
        side: str,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> Order:
        """创建订单"""
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
        """取消订单"""
        order = self._orders.get(order_id)
        if order and order.status in (OrderStatus.PENDING, OrderStatus.OPEN):
            order.status = OrderStatus.CANCELLED
            order.updated_at = datetime.now(timezone.utc).isoformat()
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
