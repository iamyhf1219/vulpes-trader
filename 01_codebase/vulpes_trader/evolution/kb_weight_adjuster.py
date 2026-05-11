"""KB 权重调节器 — 知识库规则影响信号融合权重

工作原理:
1. 查询知识库中与当前交易对/市场相关的活跃规则
2. 根据规则内容匹配当前上下文（币种、方向、市场状态）
3. 输出权重调整量，应用到 SignalFusionEngine
"""

import logging
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger("vulpes.evolution.kb_weight")


# 预定义的币种-标签映射（后续可由知识库自动扩展）
SYMBOL_TAGS = {
    "BTC": ["BTC", "比特币", "大盘"],
    "ETH": ["ETH", "以太坊"],
    "SOL": ["SOL", "Solana"],
    "BNB": ["BNB", "币安"],
    "DOGE": ["DOGE", "狗狗币"],
    "XRP": ["XRP", "瑞波"],
    "LINK": ["LINK", "Chainlink"],
    "ADA": ["ADA", "Cardano"],
}


@dataclass
class WeightAdjustment:
    """单次权重调整记录"""
    source: str         # 影响的信号源: trend / heat / event / oi
    delta: float        # 权重增量 (-0.2 ~ +0.2)
    reason: str         # 调整原因
    rule_id: int        # 触发的 KB 规则 ID


class KBWeightAdjuster:
    """
    知识库驱动的权重调节器
    
    在每轮信号融合前调用 apply()，获取当前应该使用的权重调整。
    """

    def __init__(self):
        self._last_adjustments: List[WeightAdjustment] = []
        self._kb = None  # 运行时由外部注入

    def bind_knowledge_base(self, kb):
        """绑定知识库实例"""
        self._kb = kb

    def apply(
        self,
        symbol: str,
        current_signals: Optional[List[Dict]] = None,
    ) -> Dict[str, float]:
        """
        根据 KB 规则计算权重调整

        Args:
            symbol: 当前交易对 (如 BTC/USDT)
            current_signals: 当前信号列表（可选的上下文）

        Returns:
            权重调整字典: {"trend": +0.05, "heat": -0.03, ...}
        """
        adjustments = {"trend": 0.0, "heat": 0.0, "event": 0.0, "oi": 0.0}
        self._last_adjustments = []

        if not self._kb:
            return adjustments

        # 提取币种简称
        base_coin = symbol.split("/")[0] if "/" in symbol else symbol
        coin_tags = SYMBOL_TAGS.get(base_coin.upper(), [base_coin])

        # 获取活跃规则
        active_rules = self._kb.get_active_rules()
        if not active_rules:
            return adjustments

        # 对每条规则评估是否影响当前交易
        for rule in active_rules:
            rule_text = rule.rule_text.lower()
            rule_tags = [t.lower() for t in (rule.tags or [])]

            # 检查规则是否匹配当前币种
            coin_match = any(
                tag.lower() in rule_text or tag.lower() in rule_tags
                for tag in coin_tags
            )

            if not coin_match:
                continue

            # 按规则类型计算权重调整
            adj = self._evaluate_rule(rule, base_coin)
            if adj:
                source, delta = adj
                # 限制单次调整幅度
                delta = max(-0.15, min(0.15, delta))
                adjustments[source] = adjustments.get(source, 0.0) + delta
                self._last_adjustments.append(WeightAdjustment(
                    source=source, delta=round(delta, 3),
                    reason=rule.rule_text[:40],
                    rule_id=rule.id,
                ))

        # 确保总调整不越界（各源权重最终范围 0.05 ~ 0.55）
        for source in adjustments:
            adjustments[source] = round(max(-0.20, min(0.20, adjustments[source])), 3)

        if any(v != 0.0 for v in adjustments.values()):
            logger.info(
                "KB权重调整 [%s]: trend=%.3f heat=%.3f event=%.3f oi=%.3f",
                symbol, adjustments["trend"], adjustments["heat"],
                adjustments["event"], adjustments["oi"],
            )

        return adjustments

    def _evaluate_rule(
        self, rule, coin: str
    ) -> Optional[Tuple[str, float]]:
        """
        评估单条规则对哪个信号源产生多少权重影响

        规则分类:
        - whale/主力/庄家 → heat 权重提升（关注市场热度异常）
        - 趋势/均线/金叉 → trend 权重提升
        - 新闻/消息/事件 → event 权重提升
        - OI/持仓量 → oi 权重提升
        - 风险/风控 → trend 权重降低（保守）
        """
        text = rule.rule_text.lower()
        cat = rule.category.lower()

        # 庄家/主力行为 → 热度分析更重要
        if cat == "whale" or any(w in text for w in ["庄家", "主力", "吸筹", "出货", "拉盘"]):
            return ("heat", 0.10)

        # 市场周期性 → 趋势更重要
        if cat == "market" or any(w in text for w in ["减半", "周期性", "趋势"]):
            return ("trend", 0.08)

        # 信号类规则 → 根据具体内容判断
        if cat == "signal" or any(w in text for w in ["信号", "金叉", "死叉", "突破"]):
            return ("trend", 0.05)

        # 事件驱动
        if any(w in text for w in ["新闻", "消息", "事件", "ETF", "监管"]):
            return ("event", 0.08)

        # 持仓量/OI
        if any(w in text for w in ["oi", "持仓量", "未平仓"]):
            return ("oi", 0.06)

        # 风险规则 → 降低趋势权重（更保守）
        if cat == "risk" or any(w in text for w in ["风险", "亏损", "止损"]):
            return ("trend", -0.05)

        return None

    def get_last_adjustments(self) -> List[WeightAdjustment]:
        """获取最近一次权重调整记录"""
        return list(self._last_adjustments)

    def to_dict(self) -> Dict:
        return {
            "adjustments": [
                {"source": a.source, "delta": a.delta, "reason": a.reason, "rule_id": a.rule_id}
                for a in self._last_adjustments
            ],
            "active_rules_count": len(self._kb.get_active_rules()) if self._kb else 0,
        }
