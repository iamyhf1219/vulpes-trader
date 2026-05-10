"""币安广场热度监控 — 爬取广场热点 Ticker"""

import asyncio
import logging
from typing import List, Optional, Dict, Callable
from dataclasses import dataclass
from datetime import datetime
import aiohttp

logger = logging.getLogger("vulpes.square")


@dataclass
class TickerHeatRank:
    ticker: str
    mentions: int
    sources: int         # 信号源数（广场/帖子/社区）
    momentum: str        # 'rising' | 'stable' | 'falling'
    oi_change: str       # 'extreme' | 'strong' | 'moderate' | 'none'
    price_change_1h: float = 0.0


class SquareMonitor:
    """
    币安广场热度监控
    
    Phase A: 通过币安公开 API 获取
    Phase B+: 增加爬虫/WebSocket 实时流
    """

    BASE_URL = "https://www.binance.com/bapi/square/v1/public/square"

    def __init__(self, poll_interval: int = 30, max_tickers: int = 30):
        self.poll_interval = poll_interval
        self.max_tickers = max_tickers
        self._session: Optional[aiohttp.ClientSession] = None
        self._ticker_rank: List[TickerHeatRank] = []
        self._running = False
        self._handlers: List[Callable] = []

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    async def fetch_hot_topics(self) -> List[Dict]:
        """获取币安广场热门话题"""
        await self._ensure_session()
        try:
            async with self._session.get(
                f"{self.BASE_URL}/topic/list",
                params={"pageNo": 1, "pageSize": 50},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("data", {}).get("topics", [])
                logger.warning("广场API返回状态码: %d", resp.status)
                return []
        except Exception as e:
            logger.warning("获取广场热点失败: %s", e)
            return []

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
            if total > 0:
                momentum = "rising" if i < total // 3 else "stable" if i < total * 2 // 3 else "falling"
            else:
                momentum = "stable"
            rankings.append(TickerHeatRank(
                ticker=ticker,
                mentions=count,
                sources=1 if count < 50 else 2 if count < 100 else 3,
                momentum=momentum,
                oi_change="none",
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
                    logger.debug(
                        "广场热度更新: %d 个 Ticker", len(self._ticker_rank)
                    )
            except Exception as e:
                logger.error("热度监控异常: %s", e)
            await asyncio.sleep(self.poll_interval)

    def get_current_rankings(self) -> List[TickerHeatRank]:
        """获取当前热度排名"""
        return self._ticker_rank

    def on_update(self, handler: Callable):
        """注册更新回调"""
        self._handlers.append(handler)

    async def close(self):
        """安全关闭"""
        self._running = False
        if self._session and not self._session.closed:
            await self._session.close()
