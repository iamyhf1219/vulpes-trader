"""风控管理器 — 杠杆计算、仓位规模、动态风险控制"""

import logging
from typing import Dict, Optional, Tuple
from vulpes_trader.risk.circuit_breaker import CircuitBreaker

logger = logging.getLogger("vulpes.risk")


class RiskManager:
    """
    风控管理器
    
    核心功能:
    - 动态杠杆计算（基于波动率、流动性、资金费率）
    - 动态仓位规模（基于 ATR 调整）
    - 止损计算（固定 + 移动止损）
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {
            "max_leverage": 20,
            "min_leverage": 1,
            "max_capital_per_trade_base": 0.15,
            "max_total_positions": 5,
            "stop_loss_fixed_pct": 0.05,
            "trailing_stop_activation": 0.02,
            "trailing_stop_distance": 0.015,
        }
        self.circuit_breaker = CircuitBreaker()
        self._active_positions: Dict[str, dict] = {}

    def compute_leverage(
        self,
        atr_pct: float = 2.0,
        oi_rank: float = 0.5,
        funding_rate: float = 0.0,
    ) -> int:
        """
        动态计算杠杆

        Args:
            atr_pct: ATR 百分比
            oi_rank: OI 排名 (0-1)
            funding_rate: 当前资金费率

        Returns:
            推荐杠杆倍数
        """
        if self.circuit_breaker.is_tripped():
            return 1  # 熔断中，最低杠杆

        base = self.config["max_leverage"]

        # 波动率惩罚: 波动越大杠杆越低
        vol_penalty = min(atr_pct / 5.0, 1.0)

        # 流动性奖励: OI 越高杠杆可越大
        liq_boost = min(oi_rank, 1.0)

        # 资金费率惩罚: 高费率降低杠杆
        funding_penalty = min(abs(funding_rate) * 200, 0.5)

        final = base * (1 - vol_penalty * 0.6) * liq_boost * (1 - funding_penalty)
        final = max(self.config["min_leverage"], min(final, self.config["max_leverage"]))

        return int(round(final))

    def compute_position_size(
        self,
        capital: float,
        atr_pct: float = 2.0,
        max_pct: Optional[float] = None,
    ) -> float:
        """
        计算仓位规模

        Args:
            capital: 总资金
            atr_pct: ATR 百分比（波动率）
            max_pct: 最大资金比例

        Returns:
            开仓名义价值 (USDT)
        """
        max_pct = max_pct or self.config["max_capital_per_trade_base"]

        # 波动越大仓位越小
        vol_adjustment = 1.0 / max(atr_pct, 0.5)
        adjusted_pct = max_pct * min(vol_adjustment, 3.0)

        # 限制最大仓位比例
        final_pct = min(adjusted_pct, max_pct * 2)
        return capital * final_pct

    def compute_stop_loss(
        self,
        entry_price: float,
        side: str,
        atr: float = 0,
        fixed_pct: Optional[float] = None,
    ) -> Tuple[float, float]:
        """
        计算止损价和移动止损激活价

        Returns:
            (stop_loss_price, trailing_activation_price)
        """
        pct = fixed_pct or self.config["stop_loss_fixed_pct"]
        atr_distance = atr * 2 if atr > 0 else entry_price * pct

        if side == "long":
            sl = entry_price - atr_distance
            # 移动止损激活: 上涨 trailing_activation_pct 后激活
            activation = entry_price * (1 + self.config["trailing_stop_activation"])
        else:
            sl = entry_price + atr_distance
            activation = entry_price * (1 - self.config["trailing_stop_activation"])

        return round(sl, 2), round(activation, 2)

    def can_open_position(self, symbol: str) -> bool:
        """检查是否可以开新仓"""
        if self.circuit_breaker.is_tripped():
            return False
        if len(self._active_positions) >= self.config["max_total_positions"]:
            return False
        return True

    def open_position(self, symbol: str, side: str, size: float):
        """记录开仓"""
        self._active_positions[symbol] = {"side": side, "size": size}

    def close_position(self, symbol: str):
        """记录平仓"""
        self._active_positions.pop(symbol, None)
