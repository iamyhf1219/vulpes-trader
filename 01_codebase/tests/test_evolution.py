import pytest
from vulpes_trader.evolution.reviewer import TradeReviewer, ReviewGrade, WinLossCategory
from vulpes_trader.evolution.optimizer import ParameterOptimizer
from vulpes_trader.evolution.knowledge_base import KnowledgeBase


# ─── Reviewer Tests ───

def test_review_win_trade():
    """测试盈利交易复盘"""
    reviewer = TradeReviewer()
    result = reviewer.review({
        "id": 1, "symbol": "BTC/USDT", "side": "long",
        "entry_price": 50000, "exit_price": 55000,
        "pnl": 500, "exit_reason": "take_profit",
    })
    assert result.grade in (ReviewGrade.A, ReviewGrade.B)
    assert result.pnl == 500
    assert "有效" in result.lessons[0]


def test_review_loss_trade():
    """测试亏损交易复盘"""
    reviewer = TradeReviewer()
    result = reviewer.review({
        "id": 2, "symbol": "ETH/USDT", "side": "long",
        "entry_price": 3000, "exit_price": 2800,
        "pnl": -200, "exit_reason": "stop_loss",
    })
    assert result.grade in (ReviewGrade.C, ReviewGrade.D)
    assert len(result.root_causes) > 0


def test_reviewer_win_rate():
    """测试胜率计算"""
    reviewer = TradeReviewer()
    reviewer.review({"id": 1, "symbol": "BTC", "side": "long", "entry_price": 100, "exit_price": 110, "pnl": 10, "exit_reason": "tp"})
    reviewer.review({"id": 2, "symbol": "BTC", "side": "long", "entry_price": 100, "exit_price": 90, "pnl": -10, "exit_reason": "sl"})
    assert reviewer.get_win_rate() == 0.5


# ─── Optimizer Tests ───

def test_optimizer_init():
    """测试优化器初始化"""
    opt = ParameterOptimizer()
    assert opt.params["stop_loss_fixed_pct"] == 0.05
    assert opt.params["heat_weight"] == 0.35


def test_optimizer_adjust():
    """测试参数调整"""
    opt = ParameterOptimizer()
    opt._adjust_param("stop_loss_fixed_pct", 0.07, "test")
    assert opt.params["stop_loss_fixed_pct"] == 0.07
    assert len(opt._history) == 1


def test_optimizer_bounds():
    """测试参数边界约束"""
    opt = ParameterOptimizer()
    opt._adjust_param("stop_loss_fixed_pct", 0.50, "test")
    assert opt.params["stop_loss_fixed_pct"] == 0.10  # 被上限约束


def test_optimizer_rollback():
    """测试回滚"""
    opt = ParameterOptimizer()
    opt._adjust_param("heat_weight", 0.40, "up")
    opt.rollback()
    assert opt.params["heat_weight"] == 0.35


# ─── Knowledge Base Tests ───

def test_knowledge_base_add():
    """测试添加规则"""
    kb = KnowledgeBase()
    rule = kb.add_rule("当 OI 与价格背离时，降低热度信号权重", source_trade_id=1)
    assert rule.id == 1
    assert rule.active is True


def test_knowledge_base_effectiveness():
    """测试规则有效性跟踪"""
    kb = KnowledgeBase()
    rule = kb.add_rule("测试规则", source_trade_id=1)
    for _ in range(10):
        kb.record_effectiveness(rule.id, False)
    # 效率低于30%应该自动停用
    rule2 = kb._get_rule(rule.id)
    assert rule2 is None or not rule2.active


def test_knowledge_base_generate_report():
    """测试生成报告"""
    kb = KnowledgeBase()
    kb.add_rule("规则1", source_trade_id=1, category="signal")
    kb.add_rule("规则2", source_trade_id=2, category="risk")
    report = kb.generate_lessons_report()
    assert "规则1" in report
    assert "规则2" in report
