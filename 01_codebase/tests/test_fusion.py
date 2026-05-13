import pytest
from vulpes_trader.signal.fusion import SignalFusionEngine
from vulpes_trader.signal.base import Signal, SignalDirection


def make_signal(symbol: str, direction: SignalDirection, confidence: float, source: str):
    return Signal(
        symbol=symbol, direction=direction, confidence=confidence,
        source=source, timestamp=1700000000,
    )


def test_fusion_empty():
    """测试空信号列表"""
    engine = SignalFusionEngine()
    result = engine.fuse([])
    assert result is None


def test_fusion_long():
    """测试做多融合"""
    engine = SignalFusionEngine()
    signals = [
        make_signal("BTC", SignalDirection.LONG, 0.8, "trend"),
        make_signal("BTC", SignalDirection.LONG, 0.9, "heat"),
    ]
    result = engine.fuse(signals)
    assert result is not None
    assert result.direction == SignalDirection.LONG
    assert result.source == "fusion"


def test_fusion_short():
    """测试做空融合"""
    engine = SignalFusionEngine()
    signals = [
        make_signal("BTC", SignalDirection.SHORT, 0.8, "trend"),
        make_signal("BTC", SignalDirection.SHORT, 0.7, "event"),
    ]
    result = engine.fuse(signals)
    assert result is not None
    assert result.direction == SignalDirection.SHORT


def test_fusion_conflict():
    """测试信号矛盾"""
    engine = SignalFusionEngine()
    signals = [
        make_signal("BTC", SignalDirection.LONG, 0.6, "trend"),
        make_signal("BTC", SignalDirection.SHORT, 0.6, "heat"),
    ]
    result = engine.fuse(signals)
    assert result is None  # 矛盾不交易


def test_fusion_exit_long():
    """测试退出做多信号"""
    engine = SignalFusionEngine()
    signals = [
        make_signal("BTC", SignalDirection.LONG, 0.7, "trend"),
        make_signal("BTC", SignalDirection.EXIT_LONG, 0.9, "heat"),
    ]
    result = engine.fuse(signals)
    assert result is not None
    assert result.direction == SignalDirection.EXIT_LONG


def test_fusion_per_symbol_weights():
    """不同币种加载不同融合权重"""
    fusion = SignalFusionEngine()
    fusion.load_symbol_weights("SOL/USDT:USDT")
    # SOL 使用 heat-heavy 权重
    assert fusion.weights["heat"] == 0.40


def test_fusion_weight_normalization():
    """权重归一化总和为 1.0"""
    fusion = SignalFusionEngine()
    fusion.load_symbol_weights("ETH/USDT:USDT")
    total = sum(fusion.weights.values())
    assert abs(total - 1.0) < 0.01


def test_fusion_weight_update():
    """测试权重更新"""
    engine = SignalFusionEngine()
    assert engine.weights["heat"] == 0.35
    engine.update_weights("heat", 0.40)
    assert engine.weights["heat"] == 0.40
    # 不应超过上限
    engine.update_weights("heat", 0.60)
    assert engine.weights["heat"] == 0.50
