"""波动率自适应 — ATR 计算 + 动态参数调整"""

import logging
import numpy as np
import pandas as pd
from typing import Optional

logger = logging.getLogger("vulpes.data.volatility")


class VolatilityAdapter:
    """波动率自适应计算

    用途:
    - ATR% 计算（按百分比，跨币种可比）
    - 动态 EMA 周期: 高波动 → 短周期（快响应）
    - 动态仓位: 高波动 → 小仓位
    - 动态止损: 高波动 → 宽止损
    """

    def __init__(self, period: int = 14):
        self.period = period
        self._atr_history: list = []  # 保留最近 24h 的 ATR 值

    def compute_atr(self, df: pd.DataFrame) -> Optional[float]:
        """计算当前 ATR 百分比

        ATR% = ATR / close_price * 100
        """
        if df is None or len(df) < self.period + 1:
            return None

        high = df["high"].values
        low = df["low"].values
        close = df["close"].values

        # True Range
        tr = np.zeros(len(close))
        tr[1:] = np.maximum(
            high[1:] - low[1:],
            np.maximum(
                np.abs(high[1:] - close[:-1]),
                np.abs(low[1:] - close[:-1]),
            ),
        )
        # 第一根 K 线 TR = high - low
        tr[0] = high[0] - low[0]

        # EMA 平滑 ATR
        atr = np.zeros(len(tr))
        atr[:self.period] = np.mean(tr[:self.period])
        multiplier = 2 / (self.period + 1)
        for i in range(self.period, len(tr)):
            atr[i] = (tr[i] - atr[i - 1]) * multiplier + atr[i - 1]

        atr_pct = atr[-1] / close[-1] * 100
        atr_val = float(round(atr_pct, 4))

        # 维护历史
        self._atr_history.append(atr_val)
        if len(self._atr_history) > 288:  # 24h @ 5m
            self._atr_history = self._atr_history[-288:]

        return atr_val

    def get_atr_percentile(self, atr_pct: float) -> float:
        """ATR 在近期历史中的百分位 (0.0~1.0)"""
        if not self._atr_history or len(self._atr_history) < 10:
            return 0.5
        count_less = sum(1 for a in self._atr_history if a < atr_pct)
        return count_less / len(self._atr_history)

    def adaptive_ema_period(self, base_period: int, atr_pct: float) -> int:
        """波动率大 → 缩短 EMA 周期"""
        pct = self.get_atr_percentile(atr_pct)
        # pct=0 (低波动) → base, pct=1 (高波动) → base*0.6
        factor = 1.0 - pct * 0.4
        adjusted = max(3, int(round(base_period * factor)))
        return adjusted

    def adaptive_position_size(self, base_size: float, atr_pct: float) -> float:
        """波动率大 → 减小仓位

        目标风险: 每笔交易风险 = atr_pct * 1.5
        期望风险: 2%（base）
        """
        target_risk = 2.0  # 目标每笔风险 2%
        if atr_pct <= 0:
            return base_size
        adjusted = base_size * (target_risk / (atr_pct * 1.5))
        return max(0.05, min(base_size * 2, adjusted))

    def adaptive_stop_loss(self, base_sl: float, atr_pct: float) -> float:
        """波动率大 → 放宽止损"""
        min_sl = max(base_sl, atr_pct * 1.5 / 100)
        return round(min(min_sl, 0.15), 4)
