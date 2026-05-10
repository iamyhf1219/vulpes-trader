import pytest
from vulpes_trader.data.supplementary import OIDataPoint, FundingRateDataPoint


def test_oi_datapoint():
    """测试 OIDataPoint 创建"""
    dp = OIDataPoint(symbol="BTC/USDT:USDT", oi=500000000, 
                     oi_change_pct=15.5, timestamp=1700000000)
    assert dp.symbol == "BTC/USDT:USDT"
    assert dp.oi_change_pct == 15.5
    assert dp.oi == 500000000


def test_funding_rate_datapoint():
    """测试 FundingRateDataPoint 创建"""
    dp = FundingRateDataPoint(
        symbol="ETH/USDT:USDT",
        rate=0.0001,
        next_payment_time=1700000000,
        timestamp=1699996400,
    )
    assert dp.symbol == "ETH/USDT:USDT"
    assert dp.rate == 0.0001
    assert dp.next_payment_time == 1700000000


def test_supplementary_collector_init():
    """测试 SupplementaryCollector 初始化"""
    from vulpes_trader.data.supplementary import SupplementaryCollector
    collector = SupplementaryCollector(symbols=["BTC/USDT:USDT"])
    assert len(collector.symbols) == 1
    assert collector.symbols[0] == "BTC/USDT:USDT"
    assert not collector._running
