"""事件驱动信号 — 基于新闻事件分析"""

import logging
from typing import Optional, Dict
from vulpes_trader.signal.base import SignalGenerator, Signal, SignalDirection
from vulpes_trader.data.news_engine import EventImpact

logger = logging.getLogger("vulpes.signal.event")


class EventAnalyzer(SignalGenerator):
    """
    事件驱动信号生成器
    
    将新闻事件分析结果转化为交易信号
    """

    def __init__(self, news_engine=None):
        self.news_engine = news_engine

    def name(self) -> str:
        return "event"

    async def generate(self, symbol: str) -> Optional[Signal]:
        """生成事件信号"""
        if self.news_engine is None:
            return None

        recent_events = self.news_engine.get_recent_events()
        
        # 提取与当前币种相关的最新事件
        ticker = self._symbol_to_ticker(symbol)
        relevant_events = []
        
        for eid, event in recent_events.items():
            if ticker in event.affected_tokens:
                relevant_events.append(event)

        if not relevant_events:
            return None

        # 取最新事件
        latest_event = max(relevant_events, key=lambda e: e.timestamp)

        # 将事件影响映射为信号方向
        direction_map = {
            EventImpact.BULLISH: SignalDirection.LONG,
            EventImpact.BEARISH: SignalDirection.SHORT,
        }

        direction = direction_map.get(latest_event.impact)
        if direction is None:
            return None

        confidence = latest_event.confidence * 0.9  # 轻度折扣

        return Signal(
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            source="event",
            timestamp=latest_event.timestamp,
            metadata={
                "event_id": latest_event.event_id,
                "event_category": latest_event.category.value,
                "event_text": latest_event.text[:100],
            },
        )

    @staticmethod
    def _symbol_to_ticker(symbol: str) -> str:
        """将交易对转为 Ticker，如 BTC/USDT:USDT → BTC"""
        return symbol.split("/")[0]
