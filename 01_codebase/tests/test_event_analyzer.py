import pytest
from vulpes_trader.signal.event_analyzer import EventAnalyzer
from vulpes_trader.signal.base import SignalDirection
from vulpes_trader.data.news_engine import (
    NewsEventEngine, EventImpact, EventCategory, EventAnalysis
)


def test_event_analyzer_init():
    """测试 EventAnalyzer 初始化"""
    ea = EventAnalyzer()
    assert ea.name() == "event"


def test_event_analyzer_with_news():
    """测试有新闻引擎时生成信号"""
    engine = NewsEventEngine()
    result = engine.analyze_text("Binance will list $SOL today!")
    engine._recent_events[result.event_id] = result
    
    ea = EventAnalyzer(news_engine=engine)
    import asyncio
    signal = asyncio.run(ea.generate("SOL/USDT:USDT"))
    assert signal is not None
    assert signal.direction == SignalDirection.LONG
    assert signal.source == "event"


def test_event_analyzer_no_relevant():
    """测试不相关币种"""
    engine = NewsEventEngine()
    result = engine.analyze_text("$BTC price update")
    engine._recent_events[result.event_id] = result
    
    ea = EventAnalyzer(news_engine=engine)
    import asyncio
    signal = asyncio.run(ea.generate("SOL/USDT:USDT"))
    assert signal is None


def test_event_analyzer_no_engine():
    """测试无新闻引擎"""
    ea = EventAnalyzer()
    import asyncio
    signal = asyncio.run(ea.generate("BTC/USDT:USDT"))
    assert signal is None


def test_symbol_to_ticker():
    """测试交易对转 Ticker"""
    assert EventAnalyzer._symbol_to_ticker("BTC/USDT:USDT") == "BTC"
    assert EventAnalyzer._symbol_to_ticker("ETH/USDT") == "ETH"
