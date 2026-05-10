"""新闻事件引擎 — 捕获加密新闻并映射到代币"""

import asyncio
import logging
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger("vulpes.news")


class EventImpact(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    BROAD = "broad"  # 影响整个市场


class EventCategory(Enum):
    REGULATION = "regulation"
    PARTNERSHIP = "partnership"
    HACK = "hack"
    LISTING = "listing"
    MACRO = "macro"
    WHALE = "whale"
    FUNDAMENTAL = "fundamental"


@dataclass
class EventAnalysis:
    event_id: str
    text: str
    timestamp: int
    category: EventCategory
    impact: EventImpact
    confidence: float  # 0-1
    affected_tokens: Dict[str, float]  # {ticker: confidence}
    decay_hours: float = 2.0


class NewsEventEngine:
    """
    新闻事件捕获与分析引擎
    
    Phase A: 关键词匹配 + Ticker 映射
    Phase B+: NLP 语义理解 + 影响力评分
    """

    # 基础事件关键词映射
    EVENT_PATTERNS = {
        "listing": ["listing", "上线", "list", "上币"],
        "hack": ["hack", "exploit", "被盗", "攻击", "漏洞"],
        "partnership": ["partner", "合作", "integrate", "集成", "alliance"],
        "regulation_good": ["approve", "批准", "ETF", "合规", "license"],
        "regulation_bad": ["ban", "禁止", "crackdown", "监管打击", "SEC"],
        "whale": ["whale", "巨鲸", "large transfer", "大额转出"],
    }

    # Ticker 别名映射
    TICKER_ALIASES = {
        "bitcoin": "BTC", "btc": "BTC",
        "ethereum": "ETH", "eth": "ETH",
        "solana": "SOL", "sol": "SOL",
        "binance": "BNB", "bnb": "BNB",
        "ripple": "XRP", "xrp": "XRP",
        "cardano": "ADA", "ada": "ADA",
    }

    def __init__(self):
        self._recent_events: Dict[str, EventAnalysis] = {}
        self._handlers: List[Callable] = []
        self._running = False

    def analyze_text(self, text: str, timestamp: Optional[int] = None) -> EventAnalysis:
        """
        分析文本事件

        Args:
            text: 事件文本
            timestamp: 事件时间戳（ms）

        Returns:
            EventAnalysis: 包含影响判断和受影响代币
        """
        ts = timestamp or int(datetime.now(timezone.utc).timestamp() * 1000)
        text_lower = text.lower()

        # 1. 判断事件类别
        category = EventCategory.FUNDAMENTAL
        impact = EventImpact.NEUTRAL
        for pattern_type, keywords in self.EVENT_PATTERNS.items():
            if any(kw in text_lower for kw in keywords):
                if pattern_type == "listing":
                    category, impact = EventCategory.LISTING, EventImpact.BULLISH
                elif pattern_type == "hack":
                    category, impact = EventCategory.HACK, EventImpact.BEARISH
                elif pattern_type == "partnership":
                    category, impact = EventCategory.PARTNERSHIP, EventImpact.BULLISH
                elif pattern_type == "regulation_good":
                    category, impact = EventCategory.REGULATION, EventImpact.BULLISH
                elif pattern_type == "regulation_bad":
                    category, impact = EventCategory.REGULATION, EventImpact.BEARISH
                elif pattern_type == "whale":
                    category, impact = EventCategory.WHALE, EventImpact.NEUTRAL
                break

        # 2. 提取映射代币
        tokens = self._extract_tokens(text, text_lower)

        # 3. 计算置信度
        confidence = 0.5
        if tokens:
            confidence = 0.7 if impact != EventImpact.NEUTRAL else 0.5

        event_id = f"evt_{ts}_{hash(text) % 10000}"

        return EventAnalysis(
            event_id=event_id,
            text=text[:500],
            timestamp=ts,
            category=category,
            impact=impact,
            confidence=confidence,
            affected_tokens=tokens,
            decay_hours=EventCategory.HACK == category and 6.0 or 2.0,
        )

    def _extract_tokens(self, text: str, text_lower: str) -> Dict[str, float]:
        """从文本中提取代币"""
        tokens: Dict[str, float] = {}

        # 检查 $TICKER 格式
        for word in text.split():
            if word.startswith("$") and len(word) > 1:
                ticker = word[1:].upper().strip(".,!?:;")
                if ticker.isalpha() and len(ticker) <= 10:
                    tokens[ticker] = 0.8

        # 检查别名映射
        for alias, ticker in self.TICKER_ALIASES.items():
            if alias in text_lower and ticker not in tokens:
                tokens[ticker] = 0.6

        return tokens

    async def process_event(self, text: str):
        """处理新事件，推送信号"""
        analysis = self.analyze_text(text)
        self._recent_events[analysis.event_id] = analysis
        for handler in self._handlers:
            await handler(analysis)

    def on_event(self, handler: Callable):
        """注册事件回调"""
        self._handlers.append(handler)

    def get_recent_events(self) -> Dict[str, EventAnalysis]:
        """获取最近事件"""
        return self._recent_events
