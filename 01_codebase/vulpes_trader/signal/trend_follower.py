"""趋势跟踪信号 — 基于 EMA/MACD/OI"""

import logging
from typing import Optional, List
from vulpes_trader.signal.base import SignalGenerator, Signal, SignalDirection
from vulpes_trader.config.symbol_config import SymbolConfig
from vulpes_trader.data.volatility import VolatilityAdapter

logger = logging.getLogger("vulpes.signal.trend")


class TrendFollower(SignalGenerator):
    """趋势跟踪信号生成器"""

    def __init__(self, kline_engine, symbol: str = "BTC/USDT:USDT"):
        self.kline_engine = kline_engine
        self.symbol = symbol
        self._sym_config = SymbolConfig(symbol)
        self._volatility = VolatilityAdapter(period=14)
        self._reload_params()

    def _reload_params(self):
        """从 SymbolConfig 加载参数"""
        sc = self._sym_config
        self.ema_fast = sc.get_param("ema_fast", sc.ema_fast)
        self.ema_slow = sc.get_param("ema_slow", sc.ema_slow)
        self.macd_params = sc.get_param("macd_params", sc.macd_params)

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

        # --- ATR 自适应 ---
        atr_pct = self._volatility.compute_atr(df)
        if atr_pct is not None:
            ema_fast_adjusted = [
                self._volatility.adaptive_ema_period(p, atr_pct)
                for p in self.ema_fast
            ]
            ema_slow_adjusted = [
                self._volatility.adaptive_ema_period(p, atr_pct)
                for p in self.ema_slow
            ]
        else:
            ema_fast_adjusted = self.ema_fast
            ema_slow_adjusted = self.ema_slow

        if len(closes) < max(ema_slow_adjusted[-1], 50):
            return None

        # 用自适应周期计算 EMA
        ema_fast_vals = [self._ema(closes, p) for p in ema_fast_adjusted]
        ema_slow_vals = [self._ema(closes, p) for p in ema_slow_adjusted]

        current_ema_fast = ema_fast_vals[0][-1]
        current_ema_fast2 = ema_fast_vals[1][-1] if len(ema_fast_vals) > 1 else current_ema_fast
        current_ema_slow = ema_slow_vals[0][-1]
        current_ema_slow2 = ema_slow_vals[1][-1] if len(ema_slow_vals) > 1 else current_ema_slow
        prev_ema_fast = ema_fast_vals[0][-2]
        prev_ema_fast2 = ema_fast_vals[1][-2] if len(ema_fast_vals) > 1 else prev_ema_fast
        prev_ema_slow = ema_slow_vals[0][-2]
        prev_ema_slow2 = ema_slow_vals[1][-2] if len(ema_slow_vals) > 1 else prev_ema_slow
        # --- ATR 自适应结束 ---

        # 信号逻辑
        # 金叉: 快线上穿慢线
        fast_cross_up = prev_ema_fast <= prev_ema_fast2 and current_ema_fast > current_ema_fast2
        slow_cross_up = prev_ema_fast2 <= prev_ema_slow and current_ema_fast2 > current_ema_slow

        # 死叉: 快线下穿慢线
        fast_cross_down = prev_ema_fast >= prev_ema_fast2 and current_ema_fast < current_ema_fast2
        slow_cross_down = prev_ema_fast2 >= prev_ema_slow and current_ema_fast2 < current_ema_slow

        # 趋势方向
        trend_up = current_ema_slow > current_ema_slow2
        trend_down = current_ema_slow < current_ema_slow2

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
                    "ema_fast": float(current_ema_fast),
                    "ema_slow": float(current_ema_slow),
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
                    "ema_fast": float(current_ema_fast),
                    "ema_slow": float(current_ema_slow),
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
