import pytest
from vulpes_trader.data.news_engine import (
    NewsEventEngine, EventImpact, EventCategory, EventAnalysis
)


def test_analyze_listing_event():
    """测试上币事件分析"""
    engine = NewsEventEngine()
    result = engine.analyze_text("Binance will list $SOL today!")
    assert result.impact == EventImpact.BULLISH
    assert "SOL" in result.affected_tokens
    assert result.affected_tokens["SOL"] >= 0.5


def test_analyze_hack_event():
    """测试黑客事件分析"""
    engine = NewsEventEngine()
    result = engine.analyze_text("Security: $ETH protocol exploited, 10M stolen")
    assert result.impact == EventImpact.BEARISH
    assert result.category == EventCategory.HACK
    assert result.decay_hours == 6.0


def test_analyze_partnership():
    """测试合作事件"""
    engine = NewsEventEngine()
    result = engine.analyze_text("Solana partners with Google Cloud")
    assert result.impact == EventImpact.BULLISH
    assert "SOL" in result.affected_tokens
    assert result.category == EventCategory.PARTNERSHIP


def test_analyze_neutral():
    """测试中性事件"""
    engine = NewsEventEngine()
    result = engine.analyze_text("BTC price update: currently at 50000")
    assert result.impact == EventImpact.NEUTRAL


def test_multiple_tokens():
    """测试多代币提取"""
    engine = NewsEventEngine()
    result = engine.analyze_text("$BTC and $ETH both affected by news")
    assert "BTC" in result.affected_tokens
    assert "ETH" in result.affected_tokens
    assert len(result.affected_tokens) >= 2


def test_alias_mapping():
    """测试别名映射"""
    engine = NewsEventEngine()
    result = engine.analyze_text("Ethereum network upgrade successful")
    assert "ETH" in result.affected_tokens


def test_no_ticker_text():
    """测试无 Ticker 文本"""
    engine = NewsEventEngine()
    result = engine.analyze_text("Weather is nice today")
    assert len(result.affected_tokens) == 0
    assert result.impact == EventImpact.NEUTRAL
