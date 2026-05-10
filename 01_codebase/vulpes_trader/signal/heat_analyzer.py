"""热度分析信号 — 基于币安广场热度 + OI 异动"""

import logging
from typing import Optional, List
from vulpes_trader.signal.base import SignalGenerator, Signal, SignalDirection

logger = logging.getLogger("vulpes.signal.heat")


class HeatAnalyzer(SignalGenerator):
    """
    热度分析信号生成器

    策略来源: lana 老师的币安广场热点 + OI 监控策略
    - 热度排名前 20 + OI 极端变化 + 价格上涨 → 做多
    - 热度排名前 20 + OI 极端变化 + 价格下跌 → 做空
    """

    def __init__(self, square_monitor=None, oi_collector=None):
        self.square_monitor = square_monitor
        self.oi_collector = oi_collector
        self._oi_cache = {}  # symbol -> latest OI data

    def name(self) -> str:
        return "heat"

    def update_oi(self, oi_datapoint):
        """更新 OI 数据"""
        self._oi_cache[oi_datapoint.symbol] = oi_datapoint

    async def generate(self, symbol: str) -> Optional[Signal]:
        """生成热度信号"""
        rankings = self._get_rankings()
        if not rankings:
            return None

        # 从排名中找对应币种
        rank_info = None
        for i, r in enumerate(rankings):
            if r.ticker in symbol or (f"{r.ticker}/USDT:USDT" == symbol):
                rank_info = (i + 1, r)
                break

        if rank_info is None:
            return None

        rank, rank_data = rank_info
        oi_change = rank_data.oi_change
        momentum = rank_data.momentum
        sources = rank_data.sources

        # 热度 + OI 共振做多
        if rank <= 20 and oi_change in ("extreme", "strong") and sources >= 2:
            confidence = 0.8 if oi_change == "extreme" else 0.65
            return Signal(
                symbol=symbol,
                direction=SignalDirection.LONG,
                confidence=confidence,
                source="heat",
                timestamp=rank_data.mentions,
                metadata={
                    "rank": rank,
                    "oi_change": oi_change,
                    "momentum": momentum,
                    "sources": sources,
                },
            )

        # 热度单独做多（无 OI 确认）
        if rank <= 10 and momentum == "rising":
            return Signal(
                symbol=symbol,
                direction=SignalDirection.LONG,
                confidence=0.55,
                source="heat",
                timestamp=rank_data.mentions,
                metadata={
                    "rank": rank,
                    "oi_change": oi_change,
                    "momentum": momentum,
                },
            )

        return None

    def _get_rankings(self) -> List:
        """获取当前热度排名"""
        if self.square_monitor:
            return self.square_monitor.get_current_rankings()
        return []
