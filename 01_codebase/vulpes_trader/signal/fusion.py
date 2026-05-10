"""信号融合引擎 — 多信号加权合并为最终决策"""

import logging
from typing import List, Optional, Dict
from vulpes_trader.signal.base import Signal, SignalDirection

logger = logging.getLogger("vulpes.signal.fusion")


class SignalFusionEngine:
    """
    信号融合引擎
    
    将趋势信号、热度信号、事件信号加权融合为最终决策
    
    权重配置:
    - 趋势: 0.30
    - 热度: 0.35 (最高权重，lana 策略核心)
    - 事件: 0.25
    """

    def __init__(self):
        self.weights = {
            "trend": 0.30,
            "heat": 0.35,
            "event": 0.25,
            "oi": 0.10,
        }
        self._signal_history: List[Signal] = []

    def update_weights(self, source: str, new_weight: float):
        """更新信号源权重（进化系统用）"""
        if source in self.weights:
            old = self.weights[source]
            self.weights[source] = max(0.0, min(0.5, new_weight))
            logger.info("权重更新 %s: %.2f → %.2f", source, old, self.weights[source])

    def fuse(self, signals: List[Signal]) -> Optional[Signal]:
        """
        融合多信号为最终决策

        Args:
            signals: 所有信号源生成的信号列表

        Returns:
            融合后的最终信号，或 None（无明确方向）
        """
        if not signals:
            return None

        # 按方向分组并加权
        long_weight = 0.0
        short_weight = 0.0
        exit_long_weight = 0.0
        exit_short_weight = 0.0
        metadata_combined = {}
        symbol = signals[0].symbol
        latest_ts = max(s.timestamp for s in signals)

        for sig in signals:
            w = self.weights.get(sig.source, 0.2)
            
            if sig.direction == SignalDirection.LONG:
                long_weight += w * sig.confidence
            elif sig.direction == SignalDirection.SHORT:
                short_weight += w * sig.confidence
            elif sig.direction == SignalDirection.EXIT_LONG:
                exit_long_weight += w * sig.confidence
            elif sig.direction == SignalDirection.EXIT_SHORT:
                exit_short_weight += w * sig.confidence

            metadata_combined[sig.source] = {
                "direction": sig.direction.value,
                "confidence": sig.confidence,
            }

        # 退出信号优先
        if exit_long_weight >= 0.3:
            return Signal(
                symbol=symbol, direction=SignalDirection.EXIT_LONG,
                confidence=exit_long_weight, source="fusion",
                timestamp=latest_ts, metadata=metadata_combined,
            )
        if exit_short_weight >= 0.3:
            return Signal(
                symbol=symbol, direction=SignalDirection.EXIT_SHORT,
                confidence=exit_short_weight, source="fusion",
                timestamp=latest_ts, metadata=metadata_combined,
            )

        # 做多 vs 做空
        signal_diff = long_weight - short_weight
        total_weight = long_weight + short_weight

        if total_weight < 0.2:
            return None

        if signal_diff > 0.15 and long_weight > 0.2:
            direction = SignalDirection.LONG
            confidence = min(0.95, long_weight)
        elif signal_diff < -0.15 and short_weight > 0.2:
            direction = SignalDirection.SHORT
            confidence = min(0.95, short_weight)
        else:
            return None  # 信号矛盾，不交易

        return Signal(
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            source="fusion",
            timestamp=latest_ts,
            metadata=metadata_combined,
        )

    def record_signal(self, signal: Signal):
        """记录信号历史"""
        self._signal_history.append(signal)
        if len(self._signal_history) > 1000:
            self._signal_history = self._signal_history[-500:]
