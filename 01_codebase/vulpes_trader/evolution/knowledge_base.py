"""Knowledge base — learn from trade experience"""

import logging
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger("vulpes.evolution.kb")


@dataclass
class Rule:
    id: int
    rule_text: str
    source_trade_id: int
    category: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    active: bool = True
    effectiveness_score: float = 0.0


class KnowledgeBase:
    def __init__(self):
        self._rules: List[Rule] = []
        self._next_id = 1
        self._rule_effectiveness: Dict[int, List[bool]] = {}

    def add_rule(self, rule_text: str, source_trade_id: int, category: str = "signal") -> Rule:
        rule = Rule(
            id=self._next_id,
            rule_text=rule_text,
            source_trade_id=source_trade_id,
            category=category,
        )
        self._next_id += 1
        self._rules.append(rule)
        logger.info("KB rule #%d: %s", rule.id, rule_text[:60])
        return rule

    def get_active_rules(self, category: Optional[str] = None) -> List[Rule]:
        rules = [r for r in self._rules if r.active]
        if category:
            rules = [r for r in rules if r.category == category]
        return rules

    def record_effectiveness(self, rule_id: int, was_helpful: bool):
        if rule_id not in self._rule_effectiveness:
            self._rule_effectiveness[rule_id] = []
        self._rule_effectiveness[rule_id].append(was_helpful)
        rule = self._get_rule(rule_id)
        if rule:
            recent = self._rule_effectiveness[rule_id][-10:]
            if len(recent) >= 5 and sum(recent) / len(recent) < 0.3:
                rule.active = False
                logger.info("rule #%d disabled (effectiveness %.0f%%)", rule_id, sum(recent)/len(recent)*100)

    def generate_lessons_report(self) -> str:
        active = self.get_active_rules()
        if not active:
            return "No knowledge yet"
        lines = ["=== Trade Knowledge Base ==="]
        signal_rules = [r for r in active if r.category == "signal"]
        risk_rules = [r for r in active if r.category == "risk"]
        exec_rules = [r for r in active if r.category == "execution"]
        if signal_rules:
            lines.append(f"[Signal] ({len(signal_rules)} rules)")
            for r in signal_rules:
                lines.append(f"  #{r.id} {r.rule_text}")
        if risk_rules:
            lines.append(f"[Risk] ({len(risk_rules)} rules)")
            for r in risk_rules:
                lines.append(f"  #{r.id} {r.rule_text}")
        if exec_rules:
            lines.append(f"[Execution] ({len(exec_rules)} rules)")
            for r in exec_rules:
                lines.append(f"  #{r.id} {r.rule_text}")
        return "\n".join(lines)

    def _get_rule(self, rule_id: int) -> Optional[Rule]:
        for r in self._rules:
            if r.id == rule_id:
                return r
        return None

    def to_dict(self) -> Dict:
        return {
            "rules": [
                {"id": r.id, "text": r.rule_text, "category": r.category, "active": r.active}
                for r in self._rules
            ],
        }
