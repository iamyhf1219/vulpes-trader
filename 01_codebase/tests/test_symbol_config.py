"""测试多币种配置系统"""

import pytest
from vulpes_trader.config.symbol_config import SymbolConfig


def test_default_params():
    """无 per_symbol 配置时使用全局默认"""
    sc = SymbolConfig("UNKNOWN/USDT:USDT")
    assert sc.ema_fast == [9, 8]
    assert sc.ema_slow == [26, 40]


def test_per_symbol_override():
    """per_symbol 配置覆盖全局"""
    sc = SymbolConfig("SOL/USDT:USDT")
    assert sc.stop_loss_pct == 0.08  # per_symbol 配置值
    assert sc.ema_fast == [9, 8]


def test_fallback_on_partial_config():
    """部分配置使用全局默认回退"""
    sc = SymbolConfig("ETH/USDT:USDT")
    assert sc.ema_fast == [12, 10]  # per_symbol 值
    assert sc.trailing_activation == 0.022  # per_symbol 值


def test_macd_returns_tuple():
    """macd_params 返回 tuple (类型安全)"""
    sc = SymbolConfig("BTC/USDT:USDT")
    macd = sc.macd_params
    assert isinstance(macd, tuple)
    assert len(macd) == 3


def test_runtime_override():
    """运行时参数覆盖不写回 yaml"""
    sc = SymbolConfig("ETH/USDT:USDT")
    sc.update_params({"ema_fast": [5, 8]})
    assert sc.get_param("ema_fast") == [5, 8]
