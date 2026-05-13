import pytest
from vulpes_trader.risk.manager import RiskManager
from vulpes_trader.risk.circuit_breaker import CircuitBreaker


def test_risk_manager_init():
    """测试 RiskManager 初始化"""
    rm = RiskManager()
    assert rm.config["max_leverage"] == 20
    assert rm.config["max_capital_per_trade_base"] == 0.15


def test_compute_leverage_normal():
    """测试正常情况杠杆计算"""
    rm = RiskManager()
    lev = rm.compute_leverage(atr_pct=2.0, oi_rank=0.8, funding_rate=0.0001)
    assert 1 <= lev <= 20  # 在合理范围内


def test_compute_leverage_high_vol():
    """测试高波动率降低杠杆"""
    rm = RiskManager()
    lev_low_vol = rm.compute_leverage(atr_pct=1.0, oi_rank=0.8, funding_rate=0)
    lev_high_vol = rm.compute_leverage(atr_pct=8.0, oi_rank=0.8, funding_rate=0)
    assert lev_high_vol <= lev_low_vol  # 高波动杠杆更低


def test_compute_leverage_circuit_breaker():
    """测试熔断时杠杆为 1"""
    rm = RiskManager()
    rm.circuit_breaker._trip()
    lev = rm.compute_leverage(atr_pct=2.0, oi_rank=0.8, funding_rate=0)
    assert lev == 1


def test_position_size():
    """测试仓位计算"""
    rm = RiskManager()
    size = rm.compute_position_size(capital=10000, atr_pct=2.0)
    assert size > 0
    assert size <= 10000 * 0.3  # 不超过上限


def test_position_size_high_vol():
    """测试高波动率降低仓位"""
    rm = RiskManager()
    low_vol = rm.compute_position_size(capital=10000, atr_pct=0.5)
    high_vol = rm.compute_position_size(capital=10000, atr_pct=5.0)
    assert high_vol <= low_vol


def test_stop_loss_long():
    """测试做多止损"""
    rm = RiskManager()
    sl, act = rm.compute_stop_loss(entry_price=50000, side="long", fixed_pct=0.05)
    assert sl < 50000
    assert act > 50000


def test_stop_loss_short():
    """测试做空止损"""
    rm = RiskManager()
    sl, act = rm.compute_stop_loss(entry_price=3000, side="short", fixed_pct=0.05)
    assert sl > 3000
    assert act < 3000


def test_can_open_position():
    """测试开仓权限"""
    rm = RiskManager()
    assert rm.can_open_position("BTC/USDT")
    rm.open_position("BTC/USDT", "long", 0.1)
    assert rm._active_positions["BTC/USDT"]["side"] == "long"


def test_circuit_breaker_trip():
    """测试熔断触发"""
    cb = CircuitBreaker(max_consecutive_losses=2)
    cb.record_trade(-100)
    assert not cb.is_tripped()
    cb.record_trade(-200)
    assert not cb.is_tripped()
    cb.record_trade(-50)
    assert cb.is_tripped()


def test_risk_per_symbol_stop_loss():
    """不同币种不同止损比例"""
    rm = RiskManager()
    # SOL 波动大，止损 8%
    sl, act = rm.compute_stop_loss(100.0, "long", symbol="SOL/USDT:USDT")
    assert abs(sl - 92.0) < 0.01  # 100 * (1 - 0.08)


def test_risk_btc_stop_loss():
    """BTC 止损 5%"""
    rm = RiskManager()
    sl, act = rm.compute_stop_loss(60000.0, "long", symbol="BTC/USDT:USDT")
    assert abs(sl - 57000.0) < 0.01  # 60000 * (1 - 0.05)


def test_circuit_breaker_reset():
    """测试熔断重置"""
    cb = CircuitBreaker(cooldown_hours=1)  # 1 小时冷却，确保 trip 后不会自动重置
    cb._trip()
    assert cb.is_tripped()
    cb.reset()
    assert not cb.is_tripped()
