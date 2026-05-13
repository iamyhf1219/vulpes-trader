"""测试信号质量追踪"""

import pytest
from vulpes_trader.signal.tracker import SignalQualityTracker


def test_record_and_win_rate():
    """记录交易后胜率正确"""
    tracker = SignalQualityTracker(window=5)
    tracker.record_trade("BTC/USDT:USDT", {"trend": 0.7, "heat": 0.8}, 50.0)
    assert tracker.get_win_rate("BTC/USDT:USDT", "trend") == 1.0

    tracker.record_trade("BTC/USDT:USDT", {"trend": 0.6}, -30.0)
    assert tracker.get_win_rate("BTC/USDT:USDT", "trend") == 0.5  # 1胜1负


def test_empty_returns_neutral():
    """无数据返回中立 0.5"""
    tracker = SignalQualityTracker()
    assert tracker.get_win_rate("ANY", "trend") == 0.5


def test_weight_adjustments():
    """高胜率信号源获得正向调整"""
    tracker = SignalQualityTracker()
    tracker.record_trade("BTC", {"trend": 0.7}, 100)
    tracker.record_trade("BTC", {"trend": 0.7}, 100)
    tracker.record_trade("BTC", {"trend": 0.7}, 100)
    # 3次全胜，胜率 1.0
    adj = tracker.get_weight_adjustments("BTC")
    assert adj["trend"] > 1.0  # 正向调整


def test_apply_adjustments_normalization():
    """调整后所有权重归一化到 1.0"""
    tracker = SignalQualityTracker()
    for _ in range(10):
        tracker.record_trade("BTC", {"trend": 0.7, "heat": 0.8}, 10)
    base = {"trend": 0.30, "heat": 0.35, "event": 0.25, "oi": 0.10}
    adjusted = tracker.apply_adjustments(base, "BTC")
    total = sum(adjusted.values())
    assert abs(total - 1.0) < 0.01


def test_apply_adjustments_bounds():
    """权重下限 0.05，上限 0.50"""
    tracker = SignalQualityTracker()
    # 让 trend 一直输，heat 一直赢
    for _ in range(20):
        tracker.record_trade("BTC", {"trend": 0.7, "heat": 0.8}, 10)
        tracker.record_trade("BTC", {"trend": 0.6}, -50)
        tracker.record_trade("BTC", {"heat": 0.7}, 50)

    base = {"trend": 0.30, "heat": 0.35}
    adjusted = tracker.apply_adjustments(base, "BTC")
    for v in adjusted.values():
        assert 0.05 <= v <= 0.50


def test_should_adjust_trigger():
    """每 10 笔触发调整"""
    tracker = SignalQualityTracker(window=20)
    for i in range(9):
        tracker.record_trade("BTC", {"trend": 0.7}, 10)
        assert not tracker.should_adjust(min_trades=10)
    tracker.record_trade("BTC", {"trend": 0.7}, 10)
    assert tracker.should_adjust(min_trades=10)


def test_get_report():
    """报告格式正确"""
    tracker = SignalQualityTracker()
    for _ in range(15):
        tracker.record_trade("ETH", {"trend": 0.7}, 10)
    report = tracker.get_report("ETH")
    assert "trend" in report
    assert report["trend"]["total"] == 15
    assert report["trend"]["win_rate"] == 1.0
