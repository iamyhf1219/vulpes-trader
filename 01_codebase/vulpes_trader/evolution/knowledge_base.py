"""知识库 — 沉淀从交易中学到的规则和经验"""

import logging
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime
import json

logger = logging.getLogger("vulpes.evolution.kb")


@dataclass
class Rule:
    id: int
    rule_text: str
    source_trade_id: int
    category: str  # 'signal' | 'risk' | 'execution'
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    active: bool = True
    effectiveness_score: float = 0.0


class KnowledgeBase:
    """
    交易知识库
    
    从每笔交易中提取经验教训，沉淀为可执行的规则。
    知识库会自我验证 — 后续交易会验证旧规则的有效性。
    """

    def __init__(self):
        self._rules: List[Rule] = []
        self._next_id = 1
        self._rule_effectiveness: Dict[int, List[bool]] = {}

    def add_rule(self, rule_text: str, source_trade_id: int, category: str = "signal") -> Rule:
        """添加新规则"""
        rule = Rule(
            id=self._next_id,
            rule_text=rule_text,
            source_trade_id=source_trade_id,
            category=category,
        )
        self._next_id += 1
        self._rules.append(rule)
        logger.info("知识库新增规则 #%d: %s", rule.id, rule_text[:60])
        return rule

    def get_active_rules(self, category: Optional[str] = None) -> List[Rule]:
        """获取活跃规则"""
        rules = [r for r in self._rules if r.active]
        if category:
            rules = [r for r in rules if r.category == category]
        return rules

    def record_effectiveness(self, rule_id: int, was_helpful: bool):
        """记录规则有效性"""
        if rule_id not in self._rule_effectiveness:
            self._rule_effectiveness[rule_id] = []
        self._rule_effectiveness[rule_id].append(was_helpful)

        rule = self._get_rule(rule_id)
        if rule:
            recent = self._rule_effectiveness[rule_id][-10:]
            if len(recent) >= 5 and sum(recent) / len(recent) < 0.3:
                rule.active = False
                logger.info("规则 #%d 已停用（有效率%.0f%%）", rule_id, sum(recent)/len(recent)*100)

    def generate_lessons_report(self) -> str:
        """生成经验总结报告"""
        active = self.get_active_rules()
        if not active:
            return "暂无知识沉淀"

        report = ["📚 交易经验知识库\n"]
        signal_rules = [r for r in active if r.category == "signal"]
        risk_rules = [r for r in active if r.category == "risk"]
        exec_rules = [r for r in active if r.category == "execution"]

        if signal_rules:
            report.append(f"【信号】({len(signal_rules)}条)")
            for r in signal_rules:
                report.append(f"  • #{r.id} {r.rule_text}")
            report.append("")

        if risk_rules:
            report.append(f"【风控】({len(risk_rules)}条)")
            for r in risk_rules:
                report.append(f"  • #{r.id} {r.rule_text}")
            report.append("")

        if exec_rules:
            report.append(f"【执行】({len(exec_rules)}条)")
            for r in exec_rules:
                report.append(f"  • #{r.id} {r.rule_text}")

        return "\n".join(report)

    def _get_rule(self, rule_id: int) -> Optional[Rule]:
        for r in self._rules:
            if r.id == rule_id:
                return r
        return None

    def to_dict(self) -> Dict:
        """导出为字典"""
        return {
            "rules": [
                {"id": r.id, "text": r.rule_text, "category": r.category, "active": r.active}
                for r in self._rules
            ],
        }
