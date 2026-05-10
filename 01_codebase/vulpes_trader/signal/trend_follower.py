"""趋势跟踪信号 — 基于 EMA/MACD/OI"""

import logging
from typing import Optional
from vulpes_trader.signal.base import SignalGenerator, Signal, SignalDirection

logger = logging.getLogger("vulpes.signal.trend")


class TrendFollower(SignalGenerator):
    """趋势跟踪信号生成器"""

    def __init__(self, kline_engine):
        self.kline_engine = kline_engine
        self.ema_fast = [9, 12]
        self.ema_slow = [26, 50]
        self.macd_params = (12, 26, 9)

    def name(self) -> str:
        return "trend"

    async def generate(self, symbol: str) -> Optional[Signal]:
        """
        基于 EMA 交叉 + MACD 确认生成趋势信号
        
        使用主力时间框进行分析
        """
        df = self.kline_engine.get_klines(symbol, "5m")
        if df is None or len(df) < 50:
            return None

        closes = df["close"].values
        if len(closes) < 50:
            return None

        # 计算 EMA
        ema_9 = self._ema(closes, 9)
        ema_12 = self._ema(closes, 12)
        ema_26 = self._ema(closes, 26)
        ema_50 = self._ema(closes, 50)

        current_ema_9 = ema_9[-1]
        current_ema_12 = ema_12[-1]
        current_ema_26 = ema_26[-1]
        current_ema_50 = ema_50[-1]
        prev_ema_9 = ema_9[-2]
        prev_ema_12 = ema_12[-2]
        prev_ema_26 = ema_26[-2]
        prev_ema_50 = ema_50[-2]

        # 信号逻辑
        # 金叉: 快线(9,12)上穿慢线(26,50)
        fast_cross_up = prev_ema_9 <= prev_ema_12 and current_ema_9 > current_ema_12
        slow_cross_up = prev_ema_12 <= prev_ema_26 and current_ema_12 > current_ema_26

        # 死叉: 快线下穿慢线
        fast_cross_down = prev_ema_9 >= prev_ema_12 and current_ema_9 < current_ema_12
        slow_cross_down = prev_ema_12 >= prev_ema_26 and current_ema_12 < current_ema_26

        # 趋势方向
        trend_up = current_ema_26 > current_ema_50
        trend_down = current_ema_26 < current_ema_50

        # 生成信号
        if fast_cross_up and trend_up:
            confidence = 0.6 if not slow_cross_up else 0.75
            return Signal(
                symbol=symbol,
                direction=SignalDirection.LONG,
                confidence=confidence,
                source="trend",
                timestamp=int(df.iloc[-1]["timestamp"]),
                metadata={
                    "ema_9": float(current_ema_9),
                    "ema_26": float(current_ema_26),
                    "ema_50": float(current_ema_50),
                    "cross_type": "golden",
                },
            )

        if fast_cross_down and trend_down:
            confidence = 0.6 if not slow_cross_down else 0.75
            return Signal(
                symbol=symbol,
                direction=SignalDirection.SHORT,
                confidence=confidence,
                source="trend",
                timestamp=int(df.iloc[-1]["timestamp"]),
                metadata={
                    "ema_9": float(current_ema_9),
                    "ema_26": float(current_ema_26),
                    "ema_50": float(current_ema_50),
                    "cross_type": "death",
                },
            )

        # 趋势衰竭退出信号
        if trend_up and fast_cross_down:
            return Signal(
                symbol=symbol,
                direction=SignalDirection.EXIT_LONG,
                confidence=0.7,
                source="trend",
                timestamp=int(df.iloc[-1]["timestamp"]),
                metadata={"reason": "trend_exhaustion"},
            )

        if trend_down and fast_cross_up:
            return Signal(
                symbol=symbol,
                direction=SignalDirection.EXIT_SHORT,
                confidence=0.7,
                source="trend",
                timestamp=int(df.iloc[-1]["timestamp"]),
                metadata={"reason": "trend_exhaustion"},
            )

        return None

    @staticmethod
    def _ema(values, period: int):
        """计算指数移动平均"""
        result = []
        multiplier = 2 / (period + 1)
        
        # 第一个 EMA 用 SMA 初始化
        if len(values) >= period:
            ema = sum(values[:period]) / period
            result.append(ema)
            
            for price in values[period:]:
                ema = (price - ema) * multiplier + ema
                result.append(ema)
        
        return result
