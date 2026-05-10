"""熔断器 — 全局风险控制"""

import logging
import time
from typing import Optional

logger = logging.getLogger("vulpes.risk.cb")


class CircuitBreaker:
    """
    全局熔断器
    
    监控以下条件自动熔断:
    - 日亏损超过上限
    - 连续亏损超过上限
    - 总回撤超过上限
    """

    def __init__(
        self,
        daily_loss_limit: float = 0.20,
        max_consecutive_losses: int = 3,
        max_drawdown: float = 0.30,
        cooldown_hours: int = 2,
    ):
        self.daily_loss_limit = daily_loss_limit
        self.max_consecutive_losses = max_consecutive_losses
        self.max_drawdown = max_drawdown
        self.cooldown_hours = cooldown_hours

        self._tripped = False
        self._trip_time: Optional[float] = None
        self._daily_pnl = 0.0
        self._daily_reset_time = time.time()
        self._consecutive_losses = 0
        self._peak_equity = 0.0
        self._current_equity = 0.0

    def record_trade(self, pnl: float):
        """记录交易结果并检查熔断条件"""
        self._daily_pnl += pnl
        self._current_equity += pnl

        if pnl < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

        self._check_conditions()

    def update_equity(self, equity: float):
        """更新当前权益"""
        self._current_equity = equity
        if equity > self._peak_equity:
            self._peak_equity = equity

    def _check_conditions(self):
        """检查所有熔断条件"""
        # 日亏损检查
        if self._peak_equity > 0:
            if self._daily_pnl <= -self.daily_loss_limit * self._peak_equity:
                logger.warning("熔断触发: 日亏损 %.2f%%", self._daily_pnl / self._peak_equity * 100)
                self._trip()
                return

        # 连续亏损检查
        if self._consecutive_losses > self.max_consecutive_losses:
            logger.warning("熔断触发: 连续 %d 笔亏损", self._consecutive_losses)
            self._trip()
            return

        # 回撤检查
        if self._peak_equity > 0:
            drawdown = (self._peak_equity - self._current_equity) / self._peak_equity
            if drawdown >= self.max_drawdown:
                logger.warning("熔断触发: 回撤 %.2f%%", drawdown * 100)
                self._trip()

    def _trip(self):
        """触发熔断"""
        self._tripped = True
        self._trip_time = time.time()

    def is_tripped(self) -> bool:
        """检查是否熔断（考虑冷却时间）"""
        if not self._tripped:
            return False
        if self._trip_time and (time.time() - self._trip_time) > self.cooldown_hours * 3600:
            self.reset()
            return False
        return True

    def reset(self):
        """重置熔断器"""
        self._tripped = False
        self._trip_time = None
        self._consecutive_losses = 0
        logger.info("熔断器已重置")

    def reset_daily(self):
        """重置日统计（每天开始时调用）"""
        self._daily_pnl = 0.0
        self._daily_reset_time = time.time()
