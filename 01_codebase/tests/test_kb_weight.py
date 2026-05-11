"""测试 KB 权重调节器"""

import pytest
from vulpes_trader.evolution.knowledge_base import KnowledgeBase
from vulpes_trader.evolution.kb_weight_adjuster import KBWeightAdjuster


def test_adjuster_init():
    """测试初始化"""
    adj = KBWeightAdjuster()
    assert adj is not None
    assert adj.get_last_adjustments() == []


def test_adjuster_no_kb():
    """无 KB 时返回零调整"""
    adj = KBWeightAdjuster()
    result = adj.apply("BTC/USDT")
    for source in ("trend", "heat", "event", "oi"):
        assert result[source] == 0.0


def test_adjuster_with_kb():
    """有知识库时正确调整权重"""
    kb = KnowledgeBase()
    adj = KBWeightAdjuster()
    adj.bind_knowledge_base(kb)

    # 添加庄家类知识 → 提升 heat 权重
    kb.add_user_knowledge("庄家拉盘前会在关键支撑位挂大量买单", category="whale", tags=["BTC", "庄家"])
    # 添加趋势类知识 → 提升 trend 权重
    kb.add_user_knowledge("BTC减半前3个月通常有30-40%的上涨", category="market", tags=["BTC"])

    result = adj.apply("BTC/USDT")

    assert result["heat"] > 0  # 庄家规则提升 heat
    assert result["trend"] > 0  # 减半规则提升 trend
    assert len(adj.get_last_adjustments()) == 2


def test_adjuster_symbol_filter():
    """规则只影响匹配的币种"""
    kb = KnowledgeBase()
    adj = KBWeightAdjuster()
    adj.bind_knowledge_base(kb)

    kb.add_user_knowledge("SOL在$120附近放量可能是主力吸筹", category="whale", tags=["SOL"])

    # SOL 应匹配
    result_sol = adj.apply("SOL/USDT")
    assert result_sol["heat"] > 0

    # BTC 不应匹配
    result_btc = adj.apply("BTC/USDT")
    for v in result_btc.values():
        assert v == 0.0


def test_adjuster_risk_rule():
    """风险类规则降低趋势权重"""
    kb = KnowledgeBase()
    adj = KBWeightAdjuster()
    adj.bind_knowledge_base(kb)

    kb.add_rule("连续3笔亏损后应暂停交易", source_trade_id=1, category="risk", tags=["BTC"])

    result = adj.apply("BTC/USDT")

    # risk 规则应降低趋势权重（更保守）
    adjustments = adj.get_last_adjustments()
    assert adjustments[0].source == "trend"
    assert adjustments[0].delta < 0


def test_adjuster_event_rule():
    """事件类规则提升 event 权重"""
    kb = KnowledgeBase()
    adj = KBWeightAdjuster()
    adj.bind_knowledge_base(kb)

    # 事件分析类知识提 event 权重
    kb.add_user_knowledge("关注SEC对BTC ETF的监管动态", category="market", tags=["BTC"])

    result = adj.apply("BTC/USDT")

    # market 类规则默认提升 trend
    assert result["trend"] > 0


def test_weight_bounds():
    """权重调整不越界"""
    kb = KnowledgeBase()
    adj = KBWeightAdjuster()
    adj.bind_knowledge_base(kb)

    # 添加大量规则
    for i in range(20):
        kb.add_user_knowledge(f"测试规则{i}", category="whale", tags=["BTC"])

    result = adj.apply("BTC/USDT")

    for v in result.values():
        assert -0.20 <= v <= 0.20
