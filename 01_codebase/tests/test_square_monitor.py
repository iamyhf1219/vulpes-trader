import pytest
from vulpes_trader.data.square_monitor import TickerHeatRank, SquareMonitor


def test_heat_rank_creation():
    """测试 TickerHeatRank 创建"""
    rank = TickerHeatRank(ticker="LAYER", mentions=94, sources=3, 
                          momentum="rising", oi_change="extreme")
    assert rank.ticker == "LAYER"
    assert rank.mentions == 94
    assert rank.momentum == "rising"
    assert rank.oi_change == "extreme"


def test_square_monitor_init():
    """测试 SquareMonitor 初始化"""
    monitor = SquareMonitor(poll_interval=30, max_tickers=20)
    assert monitor.poll_interval == 30
    assert monitor.max_tickers == 20
    assert not monitor._running


def test_extract_tickers():
    """测试从话题中提取 Ticker"""
    monitor = SquareMonitor()
    topics = [
        {"title": "$BTC to the moon", "content": "Bitcoin is pumping"},
        {"title": "New $SOL listing", "content": "Solana ecosystem growing"},
        {"title": "$BTC analysis", "content": "BTC is looking bullish"},
    ]
    tickers = monitor.extract_tickers(topics)
    assert tickers.get("BTC") == 2
    assert tickers.get("SOL") == 1


def test_compute_rankings():
    """测试排名计算"""
    monitor = SquareMonitor(max_tickers=10)
    ticker_count = {"BTC": 50, "ETH": 30, "SOL": 20, "BNB": 10}
    rankings = monitor.compute_rankings(ticker_count)
    assert len(rankings) == 4
    assert rankings[0].ticker == "BTC"
    assert rankings[0].mentions == 50


def test_get_current_rankings_default():
    """测试默认返回空列表"""
    monitor = SquareMonitor()
    assert monitor.get_current_rankings() == []


def test_high_mentions_sources():
    """测试高提及次数的信号源数"""
    rank = TickerHeatRank(ticker="BTC", mentions=150, sources=3,
                          momentum="rising", oi_change="strong")
    assert rank.sources == 3
