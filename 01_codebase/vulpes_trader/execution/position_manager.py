"""仓位管理器 — 仓位生命周期管理"""

import logging
from typing import Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger("vulpes.execution.position")


@dataclass
class Position:
    symbol: str
    side: str  # 'long' | 'short'
    size: float  # 数量（正数）
    entry_price: float
    leverage: int = 1
    pnl: float = 0.0
    pnl_pct: float = 0.0
    opened_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    closed_at: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None


class PositionManager:
    """仓位管理器"""

    def __init__(self):
        self._positions: Dict[str, Position] = {}

    def open_position(
        self,
        symbol: str,
        side: str,
        size: float,
        entry_price: float,
        leverage: int = 1,
    ) -> Position:
        """开仓"""
        pos = Position(
            symbol=symbol,
            side=side,
            size=size,
            entry_price=entry_price,
            leverage=leverage,
        )
        self._positions[symbol] = pos
        logger.info("开仓 %s %s %.4f @%.2f (x%d)",
                     symbol, side, size, entry_price, leverage)
        return pos

    def close_position(
        self, symbol: str, exit_price: float, exit_reason: str = "manual"
    ) -> Optional[Position]:
        """平仓"""
        pos = self._positions.get(symbol)
        if pos is None:
            return None

        pos.exit_price = exit_price
        pos.exit_reason = exit_reason
        pos.closed_at = datetime.now(timezone.utc).isoformat()

        # 计算盈亏
        if pos.side == "long":
            price_diff = exit_price - pos.entry_price
        else:
            price_diff = pos.entry_price - exit_price

        pos.pnl = price_diff * pos.size * pos.leverage
        pos.pnl_pct = (price_diff / pos.entry_price) * 100 * pos.leverage

        logger.info("平仓 %s %s: pnl=%.2f (%.2f%%)",
                     symbol, exit_reason, pos.pnl, pos.pnl_pct)

        self._positions.pop(symbol)
        return pos

    def get_position(self, symbol: str) -> Optional[Position]:
        """获取当前仓位"""
        return self._positions.get(symbol)

    def has_position(self, symbol: str) -> bool:
        """是否有仓位"""
        return symbol in self._positions

    @property
    def active_positions(self) -> Dict[str, Position]:
        """获取所有活跃仓位"""
        return dict(self._positions)

    @property
    def position_count(self) -> int:
        return len(self._positions)
