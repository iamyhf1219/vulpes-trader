"""止损管理器 — 固定止损 + 移动止损"""

import logging
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger("vulpes.execution.sl")


@dataclass
class StopLossState:
    symbol: str
    side: str
    entry_price: float
    fixed_sl_price: float  # 固定止损价
    trailing_activation_price: float  # 移动止损激活价
    current_trailing_sl: Optional[float] = None  # 当前移动止损价
    highest_price: float = 0.0  # 持仓期间最高价（多头用）
    lowest_price: float = float("inf")  # 持仓期间最低价（空头用）
    activated: bool = False  # 移动止损是否已激活
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class StopLossManager:
    """
    止损管理器

    支持:
    - 固定止损（入场时设置）
    - 移动止损（达到激活价后自动追踪）
    - 分批止盈（可选）
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {
            "trailing_stop_distance": 0.015,  # 1.5%
        }
        self._positions: dict = {}

    def create_stop_loss(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        fixed_sl_pct: float = 0.05,
        trailing_activation_pct: float = 0.02,
    ) -> StopLossState:
        """创建止损"""
        if side == "long":
            fixed_sl = entry_price * (1 - fixed_sl_pct)
            activation = entry_price * (1 + trailing_activation_pct)
            highest = entry_price
            lowest = entry_price
        else:
            fixed_sl = entry_price * (1 + fixed_sl_pct)
            activation = entry_price * (1 - trailing_activation_pct)
            highest = entry_price
            lowest = entry_price

        state = StopLossState(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            fixed_sl_price=round(fixed_sl, 2),
            trailing_activation_price=round(activation, 2),
            highest_price=highest,
            lowest_price=lowest,
        )
        self._positions[symbol] = state
        logger.info("创建止损 %s %s: fixed=%.2f, trail_act=%.2f",
                     symbol, side, fixed_sl, activation)
        return state

    def update_price(self, symbol: str, current_price: float) -> Optional[float]:
        """
        更新最新价格，返回当前止损价

        会动态调整移动止损价
        """
        state = self._positions.get(symbol)
        if state is None:
            return None

        distance_pct = self.config["trailing_stop_distance"]

        if state.side == "long":
            # 更新最高价
            if current_price > state.highest_price:
                state.highest_price = current_price

            # 检查是否激活移动止损
            if not state.activated and current_price >= state.trailing_activation_price:
                state.activated = True
                trail_sl = current_price * (1 - distance_pct)
                state.current_trailing_sl = round(trail_sl, 2)
                logger.info("移动止损已激活 %s: %.2f", symbol, trail_sl)

            # 更新移动止损价
            if state.activated and state.current_trailing_sl:
                new_trail = current_price * (1 - distance_pct)
                if new_trail > state.current_trailing_sl:
                    state.current_trailing_sl = round(new_trail, 2)

            # 返回当前止损价（移动止损优先，固定止损保底）
            if state.activated and state.current_trailing_sl:
                return max(state.current_trailing_sl, state.fixed_sl_price)
            return state.fixed_sl_price

        else:
            # 更新最低价（空头）
            if current_price < state.lowest_price:
                state.lowest_price = current_price

            if not state.activated and current_price <= state.trailing_activation_price:
                state.activated = True
                trail_sl = current_price * (1 + distance_pct)
                state.current_trailing_sl = round(trail_sl, 2)
                logger.info("移动止损已激活 %s: %.2f", symbol, trail_sl)

            if state.activated and state.current_trailing_sl:
                new_trail = current_price * (1 + distance_pct)
                if new_trail < state.current_trailing_sl:
                    state.current_trailing_sl = round(new_trail, 2)

            if state.activated and state.current_trailing_sl:
                return min(state.current_trailing_sl, state.fixed_sl_price)
            return state.fixed_sl_price

    def check_stop_loss(self, symbol: str, current_price: float) -> Optional[str]:
        """
        检查是否应触发止损

        Returns:
            'fixed' | 'trailing' | None
        """
        state = self._positions.get(symbol)
        if state is None:
            return None

        sl_price = self.update_price(symbol, current_price)

        if state.side == "long" and current_price <= sl_price:
            if state.activated and state.current_trailing_sl:
                return "trailing"
            return "fixed"

        if state.side == "short" and current_price >= sl_price:
            if state.activated and state.current_trailing_sl:
                return "trailing"
            return "fixed"

        return None

    def remove(self, symbol: str):
        """移除止损"""
        self._positions.pop(symbol, None)
