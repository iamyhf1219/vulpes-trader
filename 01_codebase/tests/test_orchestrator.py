"""测试主协调器"""

import pytest
from vulpes_trader.orchestrator import VulpesOrchestrator
from vulpes_trader.signal.base import Signal, SignalDirection


def test_orchestrator_init():
    """测试 Orchestrator 初始化"""
    orch = VulpesOrchestrator()
    assert orch.db is not None
    assert orch.kline_engine is not None
    assert orch.fusion is not None
    assert orch.risk_manager is not None
    assert orch.order_manager is not None
    assert orch.position_manager is not None
    assert orch.reviewer is not None
    assert orch.optimizer is not None
    assert orch.knowledge_base is not None


def test_is_exit_signal_long():
    """测试退出信号判断"""
    orch = VulpesOrchestrator()
    exit_sig = Signal("BTC", SignalDirection.EXIT_LONG, 0.8, "fusion", 1700000000)
    assert orch._is_exit_signal(exit_sig, "long") is True
    assert orch._is_exit_signal(exit_sig, "short") is False


def test_is_exit_signal_short():
    """测试做空退出信号"""
    orch = VulpesOrchestrator()
    exit_sig = Signal("BTC", SignalDirection.EXIT_SHORT, 0.8, "fusion", 1700000000)
    assert orch._is_exit_signal(exit_sig, "short") is True
    assert orch._is_exit_signal(exit_sig, "long") is False


def test_build_signal_snapshot():
    """测试信号快照构建"""
    orch = VulpesOrchestrator()
    snapshot = orch._build_signal_snapshot("BTC/USDT")
    assert "fusion" in snapshot
    assert "params" in snapshot
