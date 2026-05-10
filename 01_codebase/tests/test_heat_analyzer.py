import pytest
from vulpes_trader.signal.heat_analyzer import HeatAnalyzer
from vulpes_trader.signal.base import SignalDirection


class MockSquareMonitor:
    def __init__(self, rankings):
        self._rankings = rankings

    def get_current_rankings(self):
        return self._rankings


def make_rank(ticker, mentions=50, sources=2, momentum="rising", oi_change="extreme"):
    """辅助创建排名对象"""
    try:
        from dataclasses import dataclass
        @dataclass
        class TickerHeatRank:
            ticker: str
            mentions: int
            sources: int
            momentum: str
            oi_change: str
            price_change_1h: float = 0.0
        return TickerHeatRank(ticker, mentions, sources, momentum, oi_change)
    except:
        class TickerHeatRank:
            def __init__(self, ticker, mentions, sources, momentum, oi_change, price_change_1h=0.0):
                self.ticker = ticker
                self.mentions = mentions
                self.sources = sources
                self.momentum = momentum
                self.oi_change = oi_change
                self.price_change_1h = price_change_1h
        return TickerHeatRank(ticker, mentions, sources, momentum, oi_change)


def test_heat_analyzer_init():
    """测试 HeatAnalyzer 初始化"""
    ha = HeatAnalyzer()
    assert ha.name() == "heat"
    assert ha._get_rankings() == []


def test_heat_signal_strong():
    """测试强热度信号（排名前20 + OI极端 + 多源）"""
    rankings = [make_rank("BTC", mentions=94, sources=3, oi_change="extreme")]
    monitor = MockSquareMonitor(rankings)
    ha = HeatAnalyzer(square_monitor=monitor)

    import asyncio
    signal = asyncio.run(ha.generate("BTC/USDT:USDT"))
    assert signal is not None
    assert signal.direction == SignalDirection.LONG
    assert signal.confidence >= 0.7
    assert signal.source == "heat"


def test_heat_signal_medium():
    """测试中等热度信号（排名10+ OI强 双源）"""
    rankings = [make_rank("SOL", mentions=60, sources=2, oi_change="strong")]
    monitor = MockSquareMonitor(rankings)
    ha = HeatAnalyzer(square_monitor=monitor)

    import asyncio
    signal = asyncio.run(ha.generate("SOL/USDT:USDT"))
    assert signal is not None
    assert signal.confidence >= 0.6


def test_heat_signal_weak():
    """测试弱热度信号（仅排名靠前）"""
    rankings = [make_rank("BNB", mentions=30, sources=1, momentum="rising", oi_change="none")]
    monitor = MockSquareMonitor(rankings)
    ha = HeatAnalyzer(square_monitor=monitor)

    import asyncio
    signal = asyncio.run(ha.generate("BNB/USDT:USDT"))
    assert signal is not None
    assert signal.confidence == 0.55


def test_heat_no_signal():
    """测试无信号（排名太低）"""
    rankings = [make_rank("XYZ", mentions=1, sources=1, momentum="falling", oi_change="none")]
    monitor = MockSquareMonitor(rankings)
    ha = HeatAnalyzer(square_monitor=monitor)

    import asyncio
    signal = asyncio.run(ha.generate("XYZ/USDT:USDT"))
    assert signal is None


def test_heat_symbol_not_found():
    """测试未找到对应币种"""
    monitor = MockSquareMonitor([make_rank("BTC", mentions=94, sources=3, oi_change="extreme")])
    ha = HeatAnalyzer(square_monitor=monitor)

    import asyncio
    signal = asyncio.run(ha.generate("UNKNOWN/USDT:USDT"))
    assert signal is None
