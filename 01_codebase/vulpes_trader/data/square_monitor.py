"""币安广场热度监控 — 模拟 + API 双模式"""

import asyncio
import logging
from typing import List, Optional, Dict, Callable
from dataclasses import dataclass
from datetime import datetime
from random import randint, uniform, choice

logger = logging.getLogger("vulpes.square")


@dataclass
class TickerHeatRank:
    ticker: str
    mentions: int
    sources: int
    momentum: str        # 'rising' | 'stable' | 'falling'
    oi_change: str       # 'extreme' | 'strong' | 'moderate' | 'none'
    price_change_1h: float = 0.0


class SquareMonitor:
    """
    市场热度监控 (模拟模式)
    
    原 Binance Square API 已不可用，使用模拟热度数据。
    后续可接入第三方热力数据源。
    """

    # 模拟的常驻热门币种
    _HOT_TICKERS = [
        "BTC", "ETH", "SOL", "BNB", "DOGE", "XRP", "ADA", "AVAX",
        "DOT", "LINK", "MATIC", "ATOM", "UNI", "ARB", "OP", "PEPE",
        "INJ", "TIA", "SEI", "SUI",
    ]

    def __init__(self, poll_interval: int = 30, max_tickers: int = 30):
        self.poll_interval = poll_interval
        self.max_tickers = max_tickers
        self._ticker_rank: List[TickerHeatRank] = []
        self._running = False
        self._handlers: List[Callable] = []

    async def fetch_hot_topics(self) -> List[Dict]:
        """生成模拟热度数据"""
        # 随机选取 8-15 个热门币种
        count = randint(8, 15)
        selected = __import__("random").sample(self._HOT_TICKERS, min(count, len(self._HOT_TICKERS)))
        return [
            {"title": f"${t} 行情分析", "content": f"${t} 近期走势强劲，关注突破"}
            for t in selected
        ]

    def extract_tickers(self, topics: List[Dict]) -> Dict[str, int]:
        """从话题中提取 Ticker 及提及次数"""
        ticker_count: Dict[str, int] = {}
        for topic in topics:
            title = topic.get("title", "")
            content = topic.get("content", "")
            text = f"{title} {content}"
            words = text.split()
            for word in words:
                if word.startswith("$") and len(word) > 1:
                    ticker = word[1:].upper().strip(".,!?:;")
                    if ticker.isalpha() and len(ticker) <= 10:
                        ticker_count[ticker] = ticker_count.get(ticker, 0) + 1
        return ticker_count

    def compute_rankings(self, ticker_count: Dict[str, int]) -> List[TickerHeatRank]:
        """计算热度排名"""
        sorted_tickers = sorted(
            ticker_count.items(), key=lambda x: x[1], reverse=True
        )[:self.max_tickers]

        rankings = []
        total = len(sorted_tickers)
        for i, (ticker, count) in enumerate(sorted_tickers):
            momentum = "rising" if i < total // 3 else "stable" if i < total * 2 // 3 else "falling"
            oi_changes = ["extreme", "strong", "moderate", "none"]
            rankings.append(TickerHeatRank(
                ticker=ticker,
                mentions=count + randint(0, 5),
                sources=randint(1, 5),
                momentum=momentum,
                oi_change=choice(oi_changes),
                price_change_1h=round(uniform(-3.0, 5.0), 2),
            ))
        return rankings

    async def start(self):
        """启动热度监控循环"""
        self._running = True
        while self._running:
            try:
                topics = await self.fetch_hot_topics()
                if topics:
                    ticker_count = self.extract_tickers(topics)
                    self._ticker_rank = self.compute_rankings(ticker_count)
                    for handler in self._handlers:
                        await handler(self._ticker_rank)
                    logger.debug("热度更新: %d 个 Ticker", len(self._ticker_rank))
            except Exception as e:
                logger.error("热度监控异常: %s", e)
            await asyncio.sleep(self.poll_interval)

    def get_current_rankings(self) -> List[TickerHeatRank]:
        return self._ticker_rank

    def on_update(self, handler: Callable):
        self._handlers.append(handler)

    async def close(self):
        self._running = False
