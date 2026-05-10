"""参数优化器 — 根据复盘结果自动调整策略参数"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from vulpes_trader.evolution.reviewer import ReviewResult

logger = logging.getLogger("vulpes.evolution.optimizer")


@dataclass
class ParameterChange:
    parameter: str
    old_value: float
    new_value: float
    reason: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class ParameterOptimizer:
    """
    参数优化器
    
    根据复盘的诊断结果，动态调整策略参数:
    - 止损宽度
    - 移动止损距离
    - 信号源权重
    - 杠杆
    
    所有调整记录在案，可回滚
    """

    def __init__(self, initial_params: Optional[Dict[str, float]] = None):
        self.params = dict(initial_params or {
            "stop_loss_fixed_pct": 0.05,
            "trailing_stop_distance": 0.015,
            "trend_weight": 0.30,
            "heat_weight": 0.35,
            "event_weight": 0.25,
            "oi_weight": 0.10,
            "max_leverage": 20,
        })
        self._history: List[ParameterChange] = []
        self._param_bounds = {
            "stop_loss_fixed_pct": (0.02, 0.10),
            "trailing_stop_distance": (0.005, 0.05),
            "trend_weight": (0.10, 0.50),
            "heat_weight": (0.10, 0.50),
            "event_weight": (0.05, 0.40),
            "oi_weight": (0.05, 0.30),
            "max_leverage": (1, 50),
        }

    def process_review(self, review: ReviewResult):
        """根据复盘结果调参"""
        for param_name, new_val in review.parameter_adjustments.items():
            self._adjust_param(param_name, new_val, f"复盘建议: {review.category.value}")

        # 持续亏损 → 降低杠杆
        if review.grade.value in ("F", "D") and review.pnl < 0:
            current_leverage = self.params.get("max_leverage", 20)
            new_leverage = max(1, int(current_leverage * 0.8))
            self._adjust_param("max_leverage", float(new_leverage),
                               f"持续亏损降杠杆: {review.category.value}")

        # 胜率高 → 可适度上调热度权重
        if review.grade in ("A", "B") and review.pnl > 0:
            current = self.params.get("heat_weight", 0.35)
            new_val = min(0.50, current + 0.02)
            self._adjust_param("heat_weight", new_val, "盈利上调热度权重")

    def _adjust_param(self, name: str, new_value: float, reason: str):
        """调整单个参数（含边界约束）"""
        if name not in self.params:
            return

        old = self.params[name]
        bounds = self._param_bounds.get(name)
        if bounds:
            new_value = max(bounds[0], min(bounds[1], new_value))

        if abs(new_value - old) < 0.001:
            return

        self.params[name] = round(new_value, 4)
        self._history.append(ParameterChange(
            parameter=name,
            old_value=old,
            new_value=self.params[name],
            reason=reason,
        ))
        logger.info("参数调整 %s: %.4f → %.4f — %s", name, old, self.params[name], reason)

    def rollback(self, n_steps: int = 1):
        """回滚最近的 N 次参数调整"""
        for _ in range(min(n_steps, len(self._history))):
            change = self._history.pop()
            self.params[change.parameter] = change.old_value
            logger.info("回滚参数 %s → %.4f", change.parameter, change.old_value)

    def get_history(self) -> List[ParameterChange]:
        """获取参数调整历史"""
        return list(self._history)
