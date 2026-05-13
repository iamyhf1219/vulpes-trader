"""信号质量追踪 — 各信号源历史胜率 + 自适应权重调整"""

import logging
from collections import defaultdict, deque
from typing import Dict, List, Optional

logger = logging.getLogger("vulpes.signal.tracker")


class SignalQualityTracker:
    """追踪各信号源历史表现，动态调整融合权重"""

    def __init__(self, window: int = 20):
        self.window = window
        # symbol -> source -> deque[bool]  (True=盈利, False=亏损)
        self._records: Dict[str, Dict[str, deque]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=100))
        )
        self._trade_count = 0

    def record_trade(self, symbol: str, signal_sources: Dict[str, float], trade_pnl: float):
        """记录一笔交易中各信号源的盈亏

        Args:
            symbol: 交易品种
            signal_sources: 信号源 -> confidence (来自 fusion metadata)
            trade_pnl: 交易盈亏（正=盈利，负=亏损）
        """
        is_win = trade_pnl > 0
        for source in signal_sources:
            self._records[symbol][source].append(is_win)
        self._trade_count += 1

    def get_win_rate(self, symbol: str, source: str, window: Optional[int] = None) -> float:
        """获取某信号源最近 N 笔胜率"""
        records = self._records.get(symbol, {}).get(source, deque())
        if not records:
            return 0.5  # 无数据时中立
        w = window or self.window
        recent = list(records)[-w:]
        if not recent:
            return 0.5
        return sum(recent) / len(recent)

    def get_weight_adjustments(self, symbol: str) -> Dict[str, float]:
        """根据历史胜率计算权重调整系数

        返回: {source: adjustment_factor}
        adjustment_factor > 1.0 表示增加权重
        """
        records = self._records.get(symbol, {})
        all_sources = list(records.keys())
        if not all_sources:
            return {}

        adjustments = {}
        for source in all_sources:
            wr = self.get_win_rate(symbol, source)
            # 胜率 > 50% 加分, < 50% 减分
            # factor = 1 + (win_rate - 0.5) * 0.5
            factor = 1.0 + (wr - 0.5) * 0.5
            # 限制调整幅度 ±20%
            factor = max(0.8, min(1.2, factor))
            adjustments[source] = round(factor, 3)

        return adjustments

    def apply_adjustments(self, base_weights: Dict[str, float],
                          symbol: str) -> Dict[str, float]:
        """应用权重调整并归一化"""
        adjustments = self.get_weight_adjustments(symbol)
        if not adjustments:
            return dict(base_weights)

        adjusted = {}
        for source, base_w in base_weights.items():
            adj_factor = adjustments.get(source, 1.0)
            new_w = base_w * adj_factor
            # 约束: min 0.05, max 0.50
            new_w = max(0.05, min(0.50, new_w))
            adjusted[source] = new_w

        # 归一化
        total = sum(adjusted.values())
        if total > 0:
            for source in adjusted:
                normalized = adjusted[source] / total
                # 归一化后再次约束
                normalized = max(0.05, min(0.50, normalized))
                adjusted[source] = round(normalized, 4)

        # 归一化后重新约束可能导致总和略小于 1.0，接受微差
        return adjusted

    def should_adjust(self, min_trades: int = 10) -> bool:
        """是否达到调整触发条件"""
        if self._trade_count == 0:
            return False
        return self._trade_count % min_trades == 0

    def get_report(self, symbol: str) -> Dict:
        """生成信号质量报告"""
        sources = self._records.get(symbol, {})
        report = {}
        for source, records in sources.items():
            recent = list(records)[-self.window:]
            report[source] = {
                "total": len(records),
                "recent": len(recent),
                "win_rate": round(self.get_win_rate(symbol, source), 3),
                "wins": sum(recent),
                "losses": len(recent) - sum(recent),
            }
        return report
